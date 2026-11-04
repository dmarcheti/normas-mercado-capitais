# Job quinzenal no launchd (Fase 4)

LaunchAgent do usuário (não daemon: o job precisa do Keychain e da sessão do `claude` logada).

## Agenda

O job roda a cada duas semanas, na quarta-feira às 13h de São Paulo (quarta sim, quarta não). A agenda está versionada em `fontes/automacao.json`: `"agenda": {"ancora": "2026-11-18", "intervalo_dias": 14, "hora": 13}`. As datas previstas são a âncora mais 14 dias vezes k: 2026-11-18, 2026-12-02, 2026-12-16 etc.

O launchd dispara o wrapper todo dia às 13h00 (`StartCalendarInterval`) e no login (`RunAtLoad`). Esses disparos só servem para recuperar uma execução perdida. Antes de qualquer rede, fetch ou worktree, o wrapper chama `job.py --checar-agenda`, que decide assim:

- roda na quarta prevista a partir das 13h, se ainda não houve execução concluída desde essa data;
- roda em qualquer horário de um dia seguinte, se a quarta prevista ficou sem execução concluída (dia perdido ou falha);
- fora disso, não roda: o log ganha uma linha (`fora da agenda; próxima prevista AAAA-MM-DD`) e o wrapper sai com 0, sem trava, sem heartbeat, sem `gh` e sem rede. Quase todo disparo termina assim, em segundos;
- antes da âncora, não roda.

Mac desligado na quarta (feriado, viagem): a execução não se perde. Ela roda no primeiro disparo depois, seja no login, seja às 13h de um dia seguinte. Mac dormindo às 13h: o launchd dispara ao acordar. Várias quartas perdidas geram uma execução só.

Execução concluída é a que chegou ao fim, mesmo fora de "ok": fonte quebrada, LLM indisponível, push bloqueado e sem token contam como feita, porque já abrem issue para o Diogo. Só a falha (saída 1, exceção, sem rede no início, falha no preparo do worktree) não conta: o wrapper tenta de novo no próximo disparo, no máximo uma tentativa por dia. A tentativa fica gravada em `ultima_tentativa` no estado.json, antes da rede: falha no fetch também conta como a tentativa do dia.

A agenda é lida do `fontes/automacao.json` do clone principal (a checagem roda antes do fetch): mudança na agenda só vale depois do pull no clone.

`--forcar` roda já, ignorando a agenda, e serve para a primeira execução manual (a R1). Uma execução forçada concluída vale como feita para a data prevista mais recente, se for no dia dela ou depois; antes da âncora, a quarta 2026-11-18 roda normalmente. Na raiz do clone (a saída vai para o log em `~/normas-auto/logs/`):

```sh
sh scripts/job_diario.sh --forcar
```

Na instalação, o `RunAtLoad` dispara uma checagem na hora do `launchctl bootstrap`. Ela só roda o job se houver execução prevista pendente; antes da âncora, ou com a execução em dia, sai com a linha de "fora da agenda" e não roda nada.

Toda execução é completa: detecção com `--frequencia todas` e `publicar` sempre. Sem `KeepAlive`: uma execução por disparo.

## Instalação e estado

O `br.normas.auto.plist` é modelo: `__REPO__` é o caminho do clone principal e `__HOME__` a pasta do usuário. O wrapper `scripts/job_diario.sh` grava o log em `~/normas-auto/logs/AAAA-MM-DD.log`; a trava fica em `~/normas-auto/job.pid` e o worktree em `~/normas-auto/worktree`. O wrapper toma a trava, prepara o worktree no `origin/main` (fetch, checkout, `clean -fd -e dados`, link `dados` para o clone) e roda o `job.py` do worktree: o código que lê o token e faz o merge é o da `main`. O job só funciona depois que o código da Fase 4 estiver na `main`.

Antes: o token no Keychain (`security add-generic-password -s normas-auto-token -a normas-auto -w`), e `fontes/automacao.json` com `"sombra": true` até o gate da fase.

O token é fine-grained, só neste repositório, com estas permissões:

| Permissão | Acesso | Para quê |
| --- | --- | --- |
| Contents | escrita | push de `auto/*` e merge |
| Pull requests | escrita | abrir, comentar e fazer o merge do PR |
| Issues | escrita | `fonte-mudou`, `perimetro`, `job-falhou`, `push-bloqueado`, `CI sem conclusão` |
| Variables | escrita | heartbeat: `ULTIMA_VERIFICACAO`, `ULTIMO_STATUS`, `EXECUCOES_SEM_OK` |
| Metadata | leitura | obrigatória |
| Actions | leitura | ler o run do `ci.yml` e os jobs `testes` e `gitleaks` |
| Commit statuses | leitura | estado do CI no commit |

Sem Actions (leitura), a API dos runs não responde, o CI fica "pendente" até esgotar os 30 min e o merge nunca sai: só a issue "CI sem conclusão".

Sem token no Keychain, o job não faz push nem lista PRs. Pela sessão do `gh` logada na máquina, grava só o heartbeat e abre as issues `fonte-mudou` e `job-falhou`.

O estado entre execuções fica em `~/normas-auto/estado.json`, fora do Git:

- `ultima_execucao_ok`: data da última execução concluída (chegou ao fim, qualquer status menos "falha"). É o que a agenda confere.
- `ultima_tentativa`: data da última tentativa decidida pela agenda (no máximo uma por dia).
- `execucoes_sem_ok`: execuções seguidas fora de "ok", que vão para `EXECUCOES_SEM_OK`. A vigia abre issue com 2 ou mais, e também quando o heartbeat (`ULTIMA_VERIFICACAO`) tem mais de 16 dias (14 da agenda e 2 de folga).

Os três comandos, rodados na raiz do clone:

1. Instalar:

   ```sh
   mkdir -p ~/normas-auto/logs && sed -e "s#__REPO__#$PWD#" -e "s#__HOME__#$HOME#" launchd/br.normas.auto.plist > ~/Library/LaunchAgents/br.normas.auto.plist && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/br.normas.auto.plist
   ```

2. Testar o disparo (só checa a agenda e roda se houver execução pendente; o log sai em `~/normas-auto/logs/`). Para rodar o job já, use o `--forcar` acima:

   ```sh
   launchctl kickstart -p gui/$(id -u)/br.normas.auto
   ```

3. Remover:

   ```sh
   launchctl bootout gui/$(id -u)/br.normas.auto && rm ~/Library/LaunchAgents/br.normas.auto.plist
   ```

Parar uma execução em curso, pelo PID exato: `kill "$(cat ~/normas-auto/job.pid)"`.
