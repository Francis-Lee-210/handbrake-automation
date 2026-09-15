# A single terminal row avoids cursor-up bookkeeping and wrapped-line drift.
typeset -gA PROGRESS=(started_at 0 completed_weight 0 last_line '')

sanitize_terminal_text() {
  print -r -- "${1//[[:cntrl:]]/?}"
}

fit_terminal_text() {
  local text="$(sanitize_terminal_text "$1")"
  local -i width=$(( ${COLUMNS:-80} - 1 ))
  local marker="..."
  (( width >= 1 )) || width=1
  (( width >= 3 )) || marker="."
  text="${text//\%/%%}"
  print -Pnr -- "%${width}>${marker}>${text}%>>"
}

render_phase() {
  [[ "$SHOW_PROGRESS" == 1 ]] || return 0
  if [[ -t 1 ]]; then
    printf '\r\033[2K%s' "$(fit_terminal_text "$1")"
  else
    sanitize_terminal_text "$1"
  fi
}

finish_phase() {
  [[ "$SHOW_PROGRESS" == 1 ]] || return 0
  render_phase "$1"
  [[ ! -t 1 ]] || print
}

format_clock() {
  local -F 6 raw_seconds="${1:-0}"
  local -i seconds=$(( raw_seconds + 0.5 ))
  (( seconds >= 0 )) || seconds=0
  printf '%02d:%02d:%02d' "$(( seconds / 3600 ))" "$(( seconds / 60 % 60 ))" "$(( seconds % 60 ))"
}

render_batch_progress() {
  [[ "$SHOW_PROGRESS" == 1 ]] || return 0
  local -i index="$1" total=${#TASK_INPUTS}
  local -F 6 percent="$2" fraction=0 remaining
  local -i elapsed=$(( SECONDS - PROGRESS[started_at] ))
  local eta="计算中" line
  (( percent < 0 )) && percent=0
  (( percent > 100 )) && percent=100
  if (( TOTAL_WEIGHT > 0 )); then
    (( fraction = (PROGRESS[completed_weight] + TASK_DURATIONS[index] * percent / 100) / TOTAL_WEIGHT ))
  fi
  (( fraction > 1 )) && fraction=1
  if (( fraction >= 1 )); then
    eta=00:00:00
  elif (( elapsed >= 10 && fraction >= 0.03 )); then
    (( remaining = elapsed * (1 - fraction) / fraction ))
    eta="$(format_clock "$remaining")"
  fi
  line="$(printf '[%d/%d] 总体 %5.1f%% | 当前 %5.1f%% | 剩余 %s | %s' \
    "$index" "$total" "$(( fraction * 100 ))" "$percent" "$eta" "${TASK_INPUTS[$index]:t}")"
  if [[ -t 1 ]]; then
    printf '\r\033[2K%s' "$(fit_terminal_text "$line")"
  elif [[ "$line" != "${PROGRESS[last_line]}" ]]; then
    sanitize_terminal_text "$line"
  fi
  PROGRESS[last_line]="$line"
}
