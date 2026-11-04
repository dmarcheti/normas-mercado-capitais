# Job diário no launchd (Fase 4)

LaunchAgent do usuário (não daemon: o job precisa do Keychain e da sessão do `claude` logada), às 07h00, por `StartCalendarInterval`. Mac desligado ou dormindo às 07h: o launchd roda ao acordar. Sem `KeepAlive`: uma execução por disparo.

O `br.normas.auto.plist` é modelo: `__REPO__` é o caminho do clone principal e `__HOME__` a pasta do usuário. O wrapper `scripts/job_diario.sh` grava o log em `~/normas-auto/logs/AAAA-MM-DD.log`; a trava fica em `~/normas-auto/job.pid` e o worktree em `~/normas-auto/worktree`. O wrapper toma a trava, prepara o worktree no `origin/main` (fetch, checkout, `clean -fd -e dados`, link `dados` para o clone) e roda o `job.py` do worktree: o código que lê o token e faz o merge é o da `main`. O job só funciona depois que o código da Fase 4 estiver na `main`.

Antes: o token no Keychain (`security add-generic-password -s normas-auto-token -a normas-auto -w`), e `fontes/automacao.json` com `"sombra": true` até o gate da fase.

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
