import {
  App,
  Editor,
  MarkdownView,
  Modal,
  Notice,
  Plugin,
  PluginSettingTab,
  Setting,
  TFile,
  TFolder,
  WorkspaceLeaf,
} from "obsidian";

import { JwToolkitClient } from "./toolkitClient";

type Length = "short" | "medium" | "long";
type Template = "plain" | "link" | "blockquote" | "callout" | "callout-collapsed";

interface JwBridgeSettings {
  apiBase: string;
  language: string;
  wtlocale: string;
  length: Length;
  template: Template;
  publication: string;
  autoLinkifyOnSave: boolean;
  includeVerseText: boolean;
}

const DEFAULT_SETTINGS: JwBridgeSettings = {
  apiBase: "http://localhost:8765",
  language: "en",
  wtlocale: "",
  length: "medium",
  template: "callout",
  publication: "nwtsty",
  autoLinkifyOnSave: false,
  includeVerseText: true,
};

export default class JwBridgePlugin extends Plugin {
  settings!: JwBridgeSettings;
  client!: JwToolkitClient;

  async onload(): Promise<void> {
    await this.loadSettings();
    this.client = new JwToolkitClient(() => this.settings.apiBase);

    this.addRibbonIcon("link", "Linkify current note", () => this.linkifyCurrentNote());

    this.addCommand({
      id: "linkify-selection",
      name: "Linkify selection",
      editorCallback: (editor) => this.linkifySelection(editor),
    });

    this.addCommand({
      id: "linkify-current-note",
      name: "Linkify current note",
      callback: () => this.linkifyCurrentNote(),
    });

    this.addCommand({
      id: "linkify-vault",
      name: "Linkify entire vault",
      callback: () => this.linkifyVault(),
    });

    this.addCommand({
      id: "convert-jwpub-current-note",
      name: "Convert jwpub:// links in current note",
      editorCallback: (editor) => this.convertJwpubLinks(editor),
    });

    this.addCommand({
      id: "insert-verse-at-cursor",
      name: "Insert Bible verse at cursor…",
      editorCallback: (editor, view) => this.insertVersePrompt(editor, view),
    });

    this.addCommand({
      id: "export-jw-library-backup",
      name: "Export JW Library backup into vault…",
      callback: () => this.exportBackupPrompt(),
    });

    this.addCommand({
      id: "index-vault-rag",
      name: "Index this vault into the toolkit RAG store",
      callback: () => this.indexVault(),
    });

    this.addCommand({
      id: "check-bridge-health",
      name: "Check bridge health",
      callback: () => this.checkHealth(),
    });

    this.registerEvent(
      this.app.vault.on("modify", (file) => {
        if (
          this.settings.autoLinkifyOnSave &&
          file instanceof TFile &&
          file.extension === "md"
        ) {
          // Debounce slightly so we don't fight the user while they type.
          window.setTimeout(() => this.linkifyFile(file, { silent: true }), 800);
        }
      })
    );

    this.addSettingTab(new JwBridgeSettingTab(this.app, this));
  }

  async loadSettings(): Promise<void> {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
  }

  // ── Commands ────────────────────────────────────────────────────────

  async linkifySelection(editor: Editor): Promise<void> {
    const selection = editor.getSelection();
    if (!selection) {
      new Notice("No selection.");
      return;
    }
    try {
      const result = await this.client.linkify(selection, this.settings);
      editor.replaceSelection(result.text);
      new Notice(`Linkified ${result.converted} reference(s).`);
    } catch (e) {
      new Notice(`Linkify failed: ${(e as Error).message}`);
    }
  }

  async linkifyCurrentNote(): Promise<void> {
    const file = this.app.workspace.getActiveFile();
    if (!file) {
      new Notice("No active note.");
      return;
    }
    await this.linkifyFile(file);
  }

  async linkifyFile(file: TFile, opts: { silent?: boolean } = {}): Promise<void> {
    try {
      const content = await this.app.vault.read(file);
      const result = await this.client.linkify(content, this.settings);
      if (result.text !== content) {
        await this.app.vault.modify(file, result.text);
      }
      if (!opts.silent) {
        new Notice(`Linkified ${result.converted} reference(s) in ${file.name}.`);
      }
    } catch (e) {
      if (!opts.silent) {
        new Notice(`Linkify failed for ${file.name}: ${(e as Error).message}`);
      }
    }
  }

  async linkifyVault(): Promise<void> {
    const files = this.app.vault.getMarkdownFiles();
    let touched = 0;
    let totalRefs = 0;
    for (const file of files) {
      try {
        const content = await this.app.vault.read(file);
        const result = await this.client.linkify(content, this.settings);
        if (result.text !== content) {
          await this.app.vault.modify(file, result.text);
          touched++;
          totalRefs += result.converted;
        }
      } catch {
        // Continue with the other files.
      }
    }
    new Notice(`Vault linkify done: ${touched} file(s) modified, ${totalRefs} ref(s).`);
  }

  async convertJwpubLinks(editor: Editor): Promise<void> {
    const content = editor.getValue();
    try {
      const result = await this.client.convertLinks(content);
      if (result.text !== content) {
        editor.setValue(result.text);
      }
      new Notice(
        `Converted ${result.bible_converted} Bible / ${result.publication_converted} publication link(s).`
      );
    } catch (e) {
      new Notice(`Convert failed: ${(e as Error).message}`);
    }
  }

  async insertVersePrompt(editor: Editor, _view: MarkdownView): Promise<void> {
    new InsertVerseModal(this.app, async (reference) => {
      if (!reference) return;
      try {
        const result = await this.client.getVerseMarkdown(reference, this.settings);
        if (result.markdown) {
          editor.replaceSelection(result.markdown + "\n");
        } else {
          new Notice(result.error || "No verse returned.");
        }
      } catch (e) {
        new Notice(`Insert verse failed: ${(e as Error).message}`);
      }
    }).open();
  }

  async exportBackupPrompt(): Promise<void> {
    new ExportBackupModal(this.app, async (backupPath, subdir) => {
      if (!backupPath) return;
      try {
        const result = await this.client.exportBackup(
          backupPath,
          this.app.vault.adapter.getResourcePath("/").replace(/^app:\/\//, "").replace(/\?.*$/, ""),
          this.settings,
          subdir
        );
        new Notice(
          `Backup export: ${result.files_written} written, ${result.files_skipped} skipped.`
        );
      } catch (e) {
        new Notice(`Backup export failed: ${(e as Error).message}`);
      }
    }).open();
  }

  async indexVault(): Promise<void> {
    const vaultPath = (this.app.vault.adapter as { getBasePath?: () => string }).getBasePath?.();
    if (!vaultPath) {
      new Notice("Vault path unavailable.");
      return;
    }
    try {
      const result = await this.client.indexVault(vaultPath);
      new Notice(
        `Indexed: ${result.indexed} new, ${result.updated} updated, ${result.deleted} deleted, ${result.unchanged} unchanged.`
      );
    } catch (e) {
      new Notice(`Index vault failed: ${(e as Error).message}`);
    }
  }

  async checkHealth(): Promise<void> {
    try {
      const ok = await this.client.health();
      new Notice(ok ? "Bridge OK ✓" : "Bridge unreachable.");
    } catch (e) {
      new Notice(`Bridge unreachable: ${(e as Error).message}`);
    }
  }
}

// ── Modals ──────────────────────────────────────────────────────────────

class InsertVerseModal extends Modal {
  private value = "";
  constructor(app: App, private onSubmit: (ref: string) => void) {
    super(app);
  }
  onOpen(): void {
    const { contentEl } = this;
    contentEl.createEl("h3", { text: "Insert Bible verse" });
    const input = contentEl.createEl("input", {
      type: "text",
      placeholder: "e.g. Juan 3:16, Mat 24:14, Rom 8:28-30",
    });
    input.style.width = "100%";
    input.addEventListener("input", () => (this.value = input.value));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.submit();
    });
    input.focus();

    const btn = contentEl.createEl("button", { text: "Insert" });
    btn.style.marginTop = "1em";
    btn.addEventListener("click", () => this.submit());
  }
  submit(): void {
    this.onSubmit(this.value.trim());
    this.close();
  }
  onClose(): void {
    this.contentEl.empty();
  }
}

class ExportBackupModal extends Modal {
  private backupPath = "";
  private subdir = "JW Library";
  constructor(
    app: App,
    private onSubmit: (backupPath: string, subdir: string) => void
  ) {
    super(app);
  }
  onOpen(): void {
    const { contentEl } = this;
    contentEl.createEl("h3", { text: "Export JW Library backup" });
    contentEl.createEl("p", {
      text: "Absolute path to a .jwlibrary file exported from the app (Settings → Backup).",
    });
    const input = contentEl.createEl("input", {
      type: "text",
      placeholder: "/Users/me/Downloads/UserDataBackup_2024.jwlibrary",
    });
    input.style.width = "100%";
    input.addEventListener("input", () => (this.backupPath = input.value));

    contentEl.createEl("p", { text: "Subdirectory under vault:" });
    const sub = contentEl.createEl("input", { type: "text", value: this.subdir });
    sub.style.width = "100%";
    sub.addEventListener("input", () => (this.subdir = sub.value));

    const btn = contentEl.createEl("button", { text: "Export" });
    btn.style.marginTop = "1em";
    btn.addEventListener("click", () => {
      this.onSubmit(this.backupPath.trim(), this.subdir.trim() || "JW Library");
      this.close();
    });
  }
  onClose(): void {
    this.contentEl.empty();
  }
}

// ── Settings tab ────────────────────────────────────────────────────────

class JwBridgeSettingTab extends PluginSettingTab {
  constructor(app: App, private plugin: JwBridgePlugin) {
    super(app, plugin);
  }
  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "JW Agent Toolkit Bridge" });

    new Setting(containerEl)
      .setName("Toolkit REST API URL")
      .setDesc("Where the jw-agent-toolkit REST server is listening.")
      .addText((t) =>
        t
          .setValue(this.plugin.settings.apiBase)
          .setPlaceholder("http://localhost:8765")
          .onChange(async (v) => {
            this.plugin.settings.apiBase = v.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Default language (ISO)")
      .setDesc("Label language for rendered references (en, es, pt, …).")
      .addText((t) =>
        t.setValue(this.plugin.settings.language).onChange(async (v) => {
          this.plugin.settings.language = v.trim();
          await this.plugin.saveSettings();
        })
      );

    new Setting(containerEl)
      .setName("wtlocale override (JW code)")
      .setDesc("Forces the `wtlocale=` URL parameter. Leave empty to follow language.")
      .addText((t) =>
        t.setValue(this.plugin.settings.wtlocale).onChange(async (v) => {
          this.plugin.settings.wtlocale = v.trim();
          await this.plugin.saveSettings();
        })
      );

    new Setting(containerEl)
      .setName("Book-name length")
      .addDropdown((d) =>
        d
          .addOptions({ short: "short", medium: "medium", long: "long" })
          .setValue(this.plugin.settings.length)
          .onChange(async (v) => {
            this.plugin.settings.length = v as Length;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Verse template")
      .addDropdown((d) =>
        d
          .addOptions({
            plain: "plain",
            link: "link",
            blockquote: "blockquote",
            callout: "callout",
            "callout-collapsed": "callout (collapsed)",
          })
          .setValue(this.plugin.settings.template)
          .onChange(async (v) => {
            this.plugin.settings.template = v as Template;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Include verse text in insert")
      .setDesc("Fetch the verse body from wol.jw.org and include it in the inserted block.")
      .addToggle((t) =>
        t.setValue(this.plugin.settings.includeVerseText).onChange(async (v) => {
          this.plugin.settings.includeVerseText = v;
          await this.plugin.saveSettings();
        })
      );

    new Setting(containerEl)
      .setName("Auto-linkify on save (experimental)")
      .setDesc("Re-linkify every .md file after modification. Useful during writing.")
      .addToggle((t) =>
        t.setValue(this.plugin.settings.autoLinkifyOnSave).onChange(async (v) => {
          this.plugin.settings.autoLinkifyOnSave = v;
          await this.plugin.saveSettings();
        })
      );
  }
}
