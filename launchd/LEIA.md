# Job diário no launchd (Fase 4)

LaunchAgent do usuário (não daemon: o job precisa do Keychain e da sessão do `claude` logada), às 07h00, por `StartCalendarInterval`. Mac desligado ou dormindo às 07h: o launchd roda ao acordar. Sem `KeepAlive`: uma execução por disparo.

O `br.normas.auto.plist` é modelo: `__REPO__` é o caminho do clone principal e `__HOME__` a pasta do usuário. O wrapper `scripts/job_diario.sh` grava o log em `~/normas-auto/logs/AAAA-MM-DD.log`; a trava fica em `~/normas-auto/job.pid` e o worktree em `~/normas-auto/worktree`. O wrapper toma a trava, prepara o worktree no `origin/main` (fetch, checkout, `clean -fd -e dados`, link `dados` para o clone) e roda o `job.py` do worktree: o código que lê o token e faz o merge é o da `main`. O job só funciona depois que o código da Fase 4 estiver na `main`.

Antes: o token no Keychain (`security add-generic-password -s normas-auto-token -a normas-auto -w`), e `fontes/automacao.json` com `"sombra": true` até o gate da fase.

O token é fine-grained, só neste repositório, com estas permissões:

| Permissão | Acesso | Para quê |
| --- | --- | --- |
| Contents | escrita | push de `auto/*` e merge |
| Pull requests | escrita | abrir, comentar e fazer o merge do PR |
| Issues | escrita | `fonte-mudou`, `perimetro`, `job-falhou`, `push-bloqueado`, `CI sem conclusão` |
| Variables | escrita | heartbeat: `ULTIMA_VERIFICACAO`, `ULTIMO_STATUS`, `DIAS_SEM_OK` |
| Metadata | leitura | obrigatória |
| Actions | leitura | ler o run do `ci.yml` e os jobs `testes` e `gitleaks` |
| Commit statuses | leitura | estado do CI no commit |

Sem Actions (leitura), a API dos runs não responde, o CI fica "pendente" até esgotar os 30 min e o merge nunca sai: só a issue "CI sem conclusão".

Sem token no Keychain, o job não faz push nem lista PRs. Pela sessão do `gh` logada na máquina, grava só o heartbeat e abre as issues `fonte-mudou` e `job-falhou`.

O estado entre execuções fica em `~/normas-auto/estado.json`, fora do Git:

- `ultima_semanal_ok`: data da última execução `todas` com todas as fontes ok. A detecção `todas` e o `publicar` rodam às segundas, ou quando essa data tem mais de 7 dias.
- `dias_sem_ok`: dias seguidos fora de "ok", que vão para `DIAS_SEM_OK`. A vigia abre issue com 3 ou mais.

Os três comandos, rodados na raiz do clone:

1. Instalar:

   ```sh
   mkdir -p ~/normas-auto/logs && sed -e "s#__REPO__#$PWD#" -e "s#__HOME__#$HOME#" launchd/br.normas.auto.plist > ~/Library/LaunchAgents/br.normas.auto.plist && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/br.normas.auto.plist
   ```

2. Testar (roda agora, sem esperar as 07h; o log sai em `~/normas-auto/logs/`):

   ```sh
   launchctl kickstart -p gui/$(id -u)/br.normas.auto
   ```

3. Remover:

   ```sh
   launchctl bootout gui/$(id -u)/br.normas.auto && rm ~/Library/LaunchAgents/br.normas.auto.plist
   ```

Parar uma execução em curso, pelo PID exato: `kill "$(cat ~/normas-auto/job.pid)"`.
