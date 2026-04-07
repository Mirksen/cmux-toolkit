/**
 * cmux-toolkit OpenCode adapter plugin.
 *
 * Translates OpenCode's hook events into the JSON-on-stdin format that
 * cmux-toolkit hook scripts expect (same format as Claude Code hooks),
 * then spawns them.
 *
 * Install: symlink or copy this directory to .opencode/plugins/cmux-toolkit
 *          or ~/.config/opencode/plugins/cmux-toolkit
 */

import type { Plugin } from "@opencode-ai/plugin"

const HOOKS_DIR = `${process.env.HOME}/.cmux-toolkit/hooks`

/** Map OpenCode lowercase tool names to PascalCase (Claude Code convention). */
function normalizeToolName(tool: string): string {
  const map: Record<string, string> = {
    edit: "Edit",
    write: "Write",
    read: "Read",
    bash: "Bash",
    apply_patch: "Edit",
  }
  return map[tool] || tool
}

/** Convert OpenCode's camelCase tool args to snake_case tool_input. */
function normalizeToolInput(
  tool: string,
  args: Record<string, any>,
): Record<string, any> {
  return {
    file_path: args.filePath || args.file_path || "",
    old_string: args.oldString || args.old_string || "",
    new_string: args.newString || args.new_string || "",
    command: args.command || "",
    content: args.content || "",
  }
}

const server: Plugin = async (ctx) => {

  /** Pipe JSON payload to a hook script via stdin (fire-and-forget). */
  function runHook(script: string, payload: Record<string, any>) {
    const json = JSON.stringify(payload)
    const path = `${HOOKS_DIR}/${script}`
    const ext = script.split(".").pop()
    const interpreter = ext === "py" ? "python3" : "bash"
    const proc = Bun.spawn([interpreter, path], {
      stdin: new Blob([json]),
      stdout: "ignore",
      stderr: "ignore",
      cwd: payload.cwd || ctx.directory,
    })
    proc.exited.catch(() => {})
  }

  return {
    // --- PostToolUse equivalent: fire after file-mutating tools ---
    "tool.execute.after": async (input, _output) => {
      const toolName = normalizeToolName(input.tool)
      if (!["Edit", "Write", "Bash"].includes(toolName)) return

      const payload = {
        session_id: input.sessionID,
        tool_name: toolName,
        tool_input: normalizeToolInput(input.tool, input.args || {}),
        cwd: ctx.directory,
      }

      runHook("view-open-file.py", payload)
    },

    // --- UserPromptSubmit equivalent: reset on new user message ---
    "chat.message": async (input, _output) => {
      // Only reset on user messages (no agent field = direct user input)
      if (input.agent) return
      const payload = { session_id: input.sessionID }
      runHook("view-prompt-reset.sh", payload)
    },

    // --- Inject cmux-toolkit env vars into shell environment ---
    "shell.env": async (input, output) => {
      if (input.sessionID) {
        output.env.CMUX_SESSION_ID = input.sessionID
      }
      // Forward cmux terminal vars (set by cmux, not the AI tool)
      for (const key of ["CMUX_WORKSPACE_ID", "CMUX_SURFACE_ID"]) {
        if (process.env[key]) {
          output.env[key] = process.env[key]!
        }
      }
    },

    // --- Session lifecycle: cleanup on exit ---
    event: async (input) => {
      const event = input.event as any
      const type = event?.type || ""

      if (type === "session.created" && event.properties?.sessionID) {
        runHook("session-init.sh", {
          session_id: event.properties.sessionID,
          cwd: ctx.directory,
        })
      }

      if (type === "session.deleted" && event.properties?.sessionID) {
        const payload = {
          session_id: event.properties.sessionID,
          reason: "exit",
        }
        runHook("session-cleanup.sh", payload)
      }
    },
  }
}

export default {
  id: "cmux-toolkit",
  server,
}
