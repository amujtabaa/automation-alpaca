#!/usr/bin/env node

/**
 * Validates that a newly created file contains required content strings.
 *
 * Hook Type: Stop
 *
 * Checks:
 * 1. Find the most recently created file in the specified directory
 * 2. Verify the file contains all required strings (case-sensitive)
 *
 * Exit codes:
 * - 0: Validation passed (file exists and contains all required strings) or error (allow through)
 * - 1: Validation failed (file missing or missing required content)
 *
 * Usage:
 *   node validate-file-contains.mjs -d specs -e .md --contains "## Task Description" --contains "## Objective"
 *   node validate-file-contains.mjs --directory output --extension .json --contains '"status":'
 */

import { execSync } from "child_process";
import { readdirSync, readFileSync, statSync } from "fs";
import { join } from "path";

const DEFAULT_DIRECTORY = ".claude/tasks";
const DEFAULT_EXTENSION = ".md";
const DEFAULT_MAX_AGE_MINUTES = 5;

const NO_FILE_ERROR = (pattern, directory) =>
  `VALIDATION FAILED: No new file found matching ${pattern}.\n\n` +
  `ACTION REQUIRED: Use the Write tool to create a new file in the ${directory}/ directory. ` +
  `The file must be created before this validation can pass. ` +
  `Do not stop until the file has been created.`;

const MISSING_CONTENT_ERROR = (file, count, missingList) =>
  `VALIDATION FAILED: File '${file}' is missing ${count} required section(s).\n\n` +
  `MISSING SECTIONS:\n${missingList}\n\n` +
  `ACTION REQUIRED: Use the Edit tool to add the missing sections to '${file}'. ` +
  `Each section must appear exactly as shown above (case-sensitive). ` +
  `Do not stop until all required sections are present in the file.`;

function getGitUntrackedFiles(directory, extension) {
  try {
    const result = execSync(`git status --porcelain "${directory}/"`, {
      encoding: "utf-8",
      timeout: 5000,
    });

    const untracked = [];
    for (const line of result.trim().split("\n")) {
      if (!line) continue;
      const status = line.substring(0, 2);
      const filepath = line.substring(3).trim();

      if (
        ["??", "A ", " A", "AM"].includes(status) &&
        filepath.endsWith(extension)
      ) {
        untracked.push(filepath);
      }
    }
    return untracked;
  } catch {
    return [];
  }
}

function getRecentFiles(directory, extension, maxAgeMinutes) {
  try {
    const files = readdirSync(directory);
    const now = Date.now();
    const maxAgeMs = maxAgeMinutes * 60 * 1000;
    const ext = extension.startsWith(".") ? extension : `.${extension}`;

    return files
      .filter((f) => f.endsWith(ext))
      .map((f) => join(directory, f))
      .filter((filepath) => {
        try {
          const mtime = statSync(filepath).mtimeMs;
          return now - mtime <= maxAgeMs;
        } catch {
          return false;
        }
      });
  } catch {
    return [];
  }
}

function findNewestFile(directory, extension, maxAgeMinutes) {
  const gitNew = getGitUntrackedFiles(directory, extension);
  const recentFiles = getRecentFiles(directory, extension, maxAgeMinutes);

  const allFiles = [...new Set([...gitNew, ...recentFiles])];
  if (allFiles.length === 0) return null;

  let newest = null;
  let newestMtime = 0;

  for (const filepath of allFiles) {
    try {
      const mtime = statSync(filepath).mtimeMs;
      if (mtime > newestMtime) {
        newestMtime = mtime;
        newest = filepath;
      }
    } catch {
      continue;
    }
  }

  return newest;
}

function checkFileContains(filepath, requiredStrings) {
  let content;
  try {
    content = readFileSync(filepath, "utf-8");
  } catch {
    return { allFound: false, found: [], missing: requiredStrings };
  }

  const found = [];
  const missing = [];

  for (const req of requiredStrings) {
    if (content.includes(req)) {
      found.push(req);
    } else {
      missing.push(req);
    }
  }

  return { allFound: missing.length === 0, found, missing };
}

function validateFileContains(directory, extension, maxAgeMinutes, requiredStrings) {
  const pattern = `${directory}/*${extension}`;

  const newestFile = findNewestFile(directory, extension, maxAgeMinutes);
  if (!newestFile) {
    return { success: false, message: NO_FILE_ERROR(pattern, directory) };
  }

  if (requiredStrings.length === 0) {
    return {
      success: true,
      message: `File found: ${newestFile} (no content checks specified)`,
    };
  }

  const { allFound, found, missing } = checkFileContains(newestFile, requiredStrings);

  if (allFound) {
    return {
      success: true,
      message: `File '${newestFile}' contains all ${requiredStrings.length} required sections`,
    };
  } else {
    const missingList = missing.map((m) => `  - ${m}`).join("\n");
    return {
      success: false,
      message: MISSING_CONTENT_ERROR(newestFile, missing.length, missingList),
    };
  }
}

// Parse args manually since parseArgs doesn't support repeated flags well
function parseCustomArgs(argv) {
  const args = {
    directory: DEFAULT_DIRECTORY,
    extension: DEFAULT_EXTENSION,
    maxAge: DEFAULT_MAX_AGE_MINUTES,
    contains: [],
  };

  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if ((arg === "-d" || arg === "--directory") && i + 1 < argv.length) {
      args.directory = argv[++i];
    } else if ((arg === "-e" || arg === "--extension") && i + 1 < argv.length) {
      args.extension = argv[++i];
    } else if (arg === "--max-age" && i + 1 < argv.length) {
      args.maxAge = parseInt(argv[++i], 10);
    } else if (arg === "--contains" && i + 1 < argv.length) {
      args.contains.push(argv[++i]);
    }
  }

  return args;
}

try {
  // Read stdin (hook input) - consume it but we don't need it
  if (!process.stdin.isTTY) {
    const chunks = [];
    process.stdin.setEncoding("utf-8");
    for await (const chunk of process.stdin) {
      chunks.push(chunk);
    }
  }

  const args = parseCustomArgs(process.argv);

  const { success, message } = validateFileContains(
    args.directory,
    args.extension,
    args.maxAge,
    args.contains
  );

  if (success) {
    console.log(JSON.stringify({ result: "continue", message }));
    process.exit(0);
  } else {
    console.log(JSON.stringify({ result: "block", reason: message }));
    process.exit(1);
  }
} catch (e) {
  console.log(
    JSON.stringify({
      result: "continue",
      message: `Validation error (allowing through): ${e.message}`,
    })
  );
  process.exit(0);
}
