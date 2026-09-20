# Configuration is data, never executable shell code.
load_video_compress_config() {
  setopt LOCAL_OPTIONS EXTENDED_GLOB
  local config_file line key value candidate resolved
  local -i line_number=0
  local -a config_keys
  local -A from_environment seen
  config_keys=(HANDBRAKECLI FFPROBE HANDBRAKE_PRESET HANDBRAKE_IMPORT_GUI
    ORIGINAL_DIR_NAME COMPRESSED_DIR_NAME LOG_FILE_NAME SHOW_PROGRESS DISABLE_NOTIFICATIONS)
  for key in "${config_keys[@]}"; do
    [[ -n "${(P)key:-}" ]] && from_environment[$key]=1
  done
  config_file="${VIDEO_COMPRESS_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/handbrake-automation/config}"
  typeset -g VIDEO_COMPRESS_CONFIG_PATH="$config_file"
  if [[ "$config_file" != none ]]; then
    if [[ -e "$config_file" || -L "$config_file" ]]; then
      [[ -f "$config_file" && -r "$config_file" ]] || {
        print -ru2 -- "Cannot read configuration: $config_file"; return 1
      }
      while IFS= read -r line || [[ -n "$line" ]]; do
        (( line_number += 1 ))
        line="${line%$'\r'}"
        line="${${line##[[:space:]]#}%%[[:space:]]#}"
        [[ -n "$line" && "$line" != \#* ]] || continue
        if [[ "$line" != *=* ]]; then
          print -ru2 -- "Invalid configuration at $config_file:$line_number (expected KEY=VALUE)"; return 1
        fi
        key="${line%%=*}"
        key="${${key##[[:space:]]#}%%[[:space:]]#}"
        if (( ! ${config_keys[(Ie)$key]} )) || [[ -n "${seen[$key]-}" ]]; then
          print -ru2 -- "Unknown or duplicate configuration key at $config_file:$line_number: $key"; return 1
        fi
        seen[$key]=1
        value="${line#*=}"
        value="${${value##[[:space:]]#}%%[[:space:]]#}"
        if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then
          value="${value[2,-2]}"
        fi
        [[ -z "${from_environment[$key]-}" ]] && typeset -g "$key=$value"
      done < "$config_file"
    elif [[ -n "${VIDEO_COMPRESS_CONFIG:-}" ]]; then
      print -ru2 -- "Configuration file does not exist: $config_file"; return 1
    fi
  fi

  typeset -g HANDBRAKE_PRESET="${HANDBRAKE_PRESET:-Fast 1080p30}"
  typeset -g HANDBRAKE_IMPORT_GUI="${HANDBRAKE_IMPORT_GUI:-0}"
  typeset -g ORIGINAL_DIR_NAME="${ORIGINAL_DIR_NAME:-原始视频}"
  typeset -g COMPRESSED_DIR_NAME="${COMPRESSED_DIR_NAME:-压缩视频}"
  typeset -g LOG_FILE_NAME="${LOG_FILE_NAME:-video-compress.log}"
  typeset -g SHOW_PROGRESS="${SHOW_PROGRESS:-0}"
  typeset -g DISABLE_NOTIFICATIONS="${DISABLE_NOTIFICATIONS:-0}"
  for key in HANDBRAKE_IMPORT_GUI SHOW_PROGRESS DISABLE_NOTIFICATIONS; do
    if [[ "${(P)key}" != (0|1) ]]; then
      print -ru2 -- "$key must be 0 or 1"; return 1
    fi
  done

  # Finder has a minimal PATH. Check both Homebrew prefixes without changing it.
  for key in HANDBRAKECLI FFPROBE; do
    candidate=HandBrakeCLI
    [[ "$key" == FFPROBE ]] && candidate=ffprobe
    value="${(P)key:-}"
    resolved=""
    if [[ -n "$value" ]]; then
      if [[ "$value" == */* ]]; then
        resolved="${value:a}"
      else
        resolved="$(whence -p -- "$value" 2>/dev/null)" || true
        [[ -n "$resolved" ]] || resolved="$value"
      fi
    else
      resolved="$(whence -p -- "$candidate" 2>/dev/null)" || true
      for value in "/opt/homebrew/bin/$candidate" "/usr/local/bin/$candidate"; do
        [[ -n "$resolved" ]] && break
        [[ -x "$value" ]] && resolved="$value"
      done
    fi
    typeset -g "$key=$resolved"
  done
}
