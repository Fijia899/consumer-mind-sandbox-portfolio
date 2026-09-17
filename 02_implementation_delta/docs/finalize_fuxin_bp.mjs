import path from "node:path";
import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";

const skillDir = "C:/Users/fkxlucky/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const workspaceDir = "D:/Xiaofeizheshapan";
const candidatePath = path.join(workspaceDir, ".codex-build-fuxin-bp", "fuxin-consumer-mind-sandbox-bp-draft.pptx");
const finalPath = path.join(workspaceDir, "outputs", "抚心消费者心智沙盘_BP.pptx");
const stagingDir = path.join(workspaceDir, ".codex-finalizer-fuxin-bp");
const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);
await fs.mkdir(stagingDir, { recursive: true });

const result = await finalizePresentation({
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: "C:/Users/fkxlucky/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe",
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
  fontPolicy: { basis: "design", families: ["Aptos"] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "抚心消费者心智沙盘_BP.validation.json"),
});
console.log(JSON.stringify(result, null, 2));
