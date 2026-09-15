# Filesystem mutations require operator-owned, non-shared path ancestry.
zmodload zsh/stat

typeset -gA LOG_FDS
typeset -gA VERIFIED_VOLUMES
typeset -ga HELD_LOCKS STAGING_DIRS

safe_component() {
  [[ -n "$1" && "$1" != . && "$1" != .. && "$1" != */* && "$1" != *[[:cntrl:]]* ]]
}

safe_acl() {
  local listing row
  local -a rows
  # -q keeps even newline-bearing filenames on the metadata line.
  listing="$(LC_ALL=C /bin/ls -ldeqn -- "$1" 2>/dev/null)" || return 1
  rows=("${(@f)listing}")
  (( ${#rows} > 0 )) || return 1
  for row in "${rows[@]:1}"; do
    [[ "$row" =~ '^[[:space:]]*[0-9]+:.* deny [a-z_,]+$' ]] || return 1
    [[ "$row" != *' allow '* ]] || return 1
  done
}

ownership_enabled() {
  local directory="$1" device_number="$2" device enabled
  [[ -n "${VERIFIED_VOLUMES[$device_number]-}" ]] && return 0
  device="$(LC_ALL=C /bin/df -P "$directory" | /usr/bin/awk 'NR == 2 { print $1 }')" || return 1
  [[ "$device" =~ '^/dev/disk[0-9]+(s[0-9]+)*$' ]] || return 1
  enabled="$(/usr/sbin/diskutil info -plist "$device" 2>/dev/null |
    /usr/bin/plutil -extract GlobalPermissionsEnabled raw -o - - 2>/dev/null)" || return 1
  [[ "$enabled" == true ]] || return 1
  VERIFIED_VOLUMES[$device_number]=1
}

safe_directory() {
  local directory="$1" current="$1"
  local -a ancestry
  local -A metadata child_metadata
  local -i index
  while true; do
    ancestry=("$current" "${ancestry[@]}")
    [[ "$current" == / ]] && break
    current="${current:h}"
  done
  for (( index = 1; index <= ${#ancestry}; index += 1 )); do
    current="${ancestry[$index]}"
    zstat -L -H metadata -- "$current" 2>/dev/null || return 1
    (( (metadata[mode] & 8#170000) == 8#40000 )) || return 1
    (( metadata[uid] == EUID || metadata[uid] == 0 )) || return 1
    ownership_enabled "$current" "$metadata[device]" || return 1
    if (( metadata[mode] & 8#22 )); then
      # A sticky ancestor is safe only for a verified operator/root-owned child.
      (( index < ${#ancestry} && metadata[mode] & 8#1000 )) || return 1
      zstat -L -H child_metadata -- "${ancestry[$(( index + 1 ))]}" 2>/dev/null || return 1
      (( child_metadata[uid] == EUID || child_metadata[uid] == 0 )) || return 1
    fi
    safe_acl "$current" || return 1
  done
}

safe_regular_file() {
  local -A metadata
  zstat -L -H metadata -- "$1" 2>/dev/null || return 1
  (( (metadata[mode] & 8#170000) == 8#100000 && metadata[nlink] == 1 && metadata[uid] == EUID && !(metadata[mode] & 8#22) )) || return 1
  safe_acl "$1"
}

safe_storage_entries() {
  local entry
  [[ -e "$1" || -L "$1" ]] || return 0
  safe_directory "$1" || return 1
  for entry in "$1"/*(DN); do
    [[ ! -L "$entry" ]] || return 1
    if [[ ! -d "$entry" ]]; then
      safe_regular_file "$entry" || return 1
    fi
  done
}

open_folder_log() {
  local log_file="$1" descriptor
  local -A metadata previous
  safe_directory "${log_file:h}" || return 1
  if [[ -e "$log_file" || -L "$log_file" ]]; then
    safe_regular_file "$log_file" || return 1
    zstat -L -H previous -- "$log_file" || return 1
    exec {descriptor}>> "$log_file" || return 1
  else
    # Protected ancestry plus exclusive creation; zsh redirections support UTF-8.
    (setopt NO_CLOBBER; umask 077; : > "$log_file") || return 1
    safe_regular_file "$log_file" || return 1
    zstat -L -H previous -- "$log_file" || return 1
    exec {descriptor}>> "$log_file" || return 1
  fi
  if ! zstat -H metadata -f "$descriptor" ||
     (( (metadata[mode] & 8#170000) != 8#100000 || metadata[nlink] != 1 || metadata[uid] != EUID || metadata[mode] & 8#22 )) ||
     (( metadata[device] != previous[device] || metadata[inode] != previous[inode] )) ||
     ! safe_regular_file "$log_file"; then
    exec {descriptor}>&-
    return 1
  fi
  LOG_FDS[$log_file]="$descriptor"
}

log_line() {
  local log_file="$1" descriptor="${LOG_FDS[$1]-}"
  shift
  [[ -n "$descriptor" ]] || return 1
  local message="$*"
  message="${message//[[:cntrl:]]/?}"
  print -r -- "$(/bin/date '+%F %T') $message" >& "$descriptor"
}

file_signature() {
  local -A metadata
  safe_regular_file "$1" || return 1
  zstat -L -H metadata -- "$1" || return 1
  print -r -- "$metadata[device]:$metadata[inode]:$metadata[size]:$metadata[mtime]:$metadata[ctime]"
}

receipt_path() {
  local digest
  digest="$(printf '%s' "${1:t}" | /usr/bin/shasum -a 256)" || return 1
  print -r -- "$2/${digest%% *}.done"
}

completed_output() {
  local input="$1" receipt="$2" compressed_dir="$3" descriptor value
  local -a fields
  [[ -f "$receipt" && ! -L "$receipt" ]] || return 1
  safe_regular_file "$receipt" || return 1
  exec {descriptor}< "$receipt" || return 1
  while IFS= read -r -d '' value <& "$descriptor"; do
    fields+=("$value")
    (( ${#fields} <= 5 )) || break
  done
  exec {descriptor}<&-
  (( ${#fields} == 5 )) || return 1
  [[ "${fields[1]}" == v1 && "${fields[2]}" == "$PRESET" ]] || return 1
  [[ "${fields[3]}" == "$(file_signature "$input")" ]] || return 1
  [[ -n "${fields[4]}" && "${fields[4]}" != */* && "${fields[4]}" != . && "${fields[4]}" != .. ]] || return 1
  local output="$compressed_dir/${fields[4]}"
  [[ -s "$output" && "${fields[5]}" == "$(file_signature "$output")" ]] || return 1
  REPLY="$output"
}

publish_output() {
  local staged="$1" output="$2" input="$3" receipt="$4" input_signature="$5"
  local output_signature
  safe_directory "${output:h}" || return 1
  safe_directory "${receipt:h}" || return 1
  safe_regular_file "$staged" && [[ -s "$staged" ]] || return 1
  [[ "$(file_signature "$input")" == "$input_signature" ]] || return 1
  [[ ! -e "$output" && ! -L "$output" ]] || return 1
  /bin/ln -n -- "$staged" "$output" || return 1
  /bin/rm -- "$staged" || return 1
  output_signature="$(file_signature "$output")" || return 1
  printf '%s\0' v1 "$PRESET" "$input_signature" "${output:t}" "$output_signature" > "${staged:h}/receipt" || return 1
  /bin/mv -f -- "${staged:h}/receipt" "$receipt"
}

cleanup_resources() {
  local entry descriptor
  for entry in "${STAGING_DIRS[@]}"; do
    /bin/rm -rf -- "$entry"
  done
  for entry in "${HELD_LOCKS[@]}"; do
    /bin/rmdir -- "$entry" 2>/dev/null || true
  done
  for descriptor in "${(@v)LOG_FDS}"; do
    exec {descriptor}>&-
  done
}
