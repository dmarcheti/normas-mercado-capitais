#!/bin/sh
# Wrapper do launchd para o job diário (Fase 4, C4). Não instala nada; ver launchd/LEIA.md.
# - PATH explícito (python3, git, gh, claude): o launchd não lê o perfil do shell.
# - Log em ~/normas-auto/logs/AAAA-MM-DD.log (acrescenta; uma execução por dia, mais as manuais).
# - Trava em ~/normas-auto/job.pid, tomada aqui antes de tocar o worktree (escrita com noclobber,
#   que é O_EXCL): outra execução viva do job faz esta sair (código 3); trava de PID morto, ou de
#   PID que não é o job, é retomada. O job.py herda a trava (--herdar) e grava o próprio PID, para
#   a parada ser pelo PID exato (kill "$(cat ~/normas-auto/job.pid)").
# - Prepara o worktree ~/normas-auto/worktree no origin/main (fetch, checkout --force num branch
#   local novo, clean sem apagar o link `dados`) e roda o job.py DO WORKTREE: o código que lê o
#   token e faz o merge é sempre o da main, nunca o desta cópia de desenvolvimento.
# - nohup caffeinate -i: o Mac não dorme durante a execução.
set -u
BASE="$HOME/normas-auto"
LOGS="$BASE/logs"
TRAVA="$BASE/job.pid"
WT="$BASE/worktree"
mkdir -p "$LOGS"
PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.claude/local:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH
CLONE=$(cd "$(dirname "$0")/.." && pwd)
LOG="$LOGS/$(date +%Y-%m-%d).log"
exec >> "$LOG" 2>&1

echo "=== $(date '+%Y-%m-%d %H:%M:%S') job_diario.sh (pid $$)"
for c in python3 git gh claude caffeinate; do
  printf '%s: %s\n' "$c" "$(command -v "$c" || echo AUSENTE)"
done

e_job() {  # PID vivo e que é o job (job.py ou este wrapper)
  kill -0 "$1" 2>/dev/null || return 1
  ps -p "$1" -o command= 2>/dev/null | grep -q -e 'job\.py' -e 'job_diario'
}
tomar() { ( set -C; echo "$$" > "$TRAVA" ) 2>/dev/null; }
if ! tomar; then
  outro=$(cat "$TRAVA" 2>/dev/null || echo 0)
  if [ -n "$outro" ] && [ "$outro" != 0 ] && e_job "$outro"; then
    echo "outra execução ativa (pid $outro): sai com 3"
    exit 3
  fi
  rm -f "$TRAVA"
  tomar || { echo "trava disputada: sai com 3"; exit 3; }
fi
trap 'rm -f "$TRAVA"' EXIT  # vale até o exec; depois, o job.py solta a trava

falha() { echo "preparo do worktree: $*"; exit 1; }
git -C "$CLONE" fetch --prune origin || falha "fetch"
if [ ! -e "$WT/.git" ]; then
  mkdir -p "$BASE"
  git -C "$CLONE" worktree add --detach "$WT" origin/main || falha "worktree add"
fi
git -C "$WT" checkout --force -B auto-execucao origin/main || falha "checkout de origin/main"
git -C "$WT" clean -fd -e dados || falha "clean"
if [ ! -e "$WT/dados" ] && [ ! -L "$WT/dados" ]; then
  ln -s "$CLONE/dados" "$WT/dados" || falha "link dados"
fi
[ -L "$WT/dados" ] || falha "$WT/dados não é link para $CLONE/dados: confira à mão"
echo "worktree em $(git -C "$WT" rev-parse HEAD) (origin/main)"

trap - EXIT
exec nohup caffeinate -i python3 "$WT/scripts/job.py" --clone "$CLONE" --worktree "$WT" \
  --trava "$TRAVA" --herdar "$$" "$@"
