# ASI3 Daemon Health Guard

Created: 2026-05-28

ASI3 daemon health showed the daemon process was up and `ready`, but its last
command marker state was stale:

- last command started: `2026-05-27T16:35:32.298Z`
- last command completed: `2026-05-26T09:56:54.515Z`
- observed failure shape: terminal command injection did not show command
  markers

To avoid hammering the degraded daemon command channel, `scripts/ASI3_shell.sh`
now checks `http://127.0.0.1:19003/health` before daemon-only shell execution.
It refuses to enqueue a command when:

- `busy` is true;
- `pendingRequestCount` is nonzero;
- `lastCommandStartedAt` is newer than `lastCommandCompletedAt`.

The override `ASI3_SKIP_DAEMON_HEALTH_GUARD=1` exists only for deliberate manual
recovery attempts. Normal MWG validation, fetch, upload, and launch scripts
should leave the guard enabled.

Validation:

```bash
ASI3_ALLOW_BROWSER=0 HUANXIN_ALLOW_STANDALONE_FALLBACK=0 \
  bash scripts/ASI3_shell.sh "printf should_not_run"
```

Result: the wrapper failed locally before sending a remote command, reporting
the incomplete previous command state. No ASI3 shell/upload/fetch helper was
left running.
