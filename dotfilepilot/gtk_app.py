"""Fenêtre GTK4 native et opérations hors du fil d’interface."""

import json
from pathlib import Path
from threading import Thread

from gi.repository import Gio, GLib, Gtk

from . import deployments as deploy
from .system import clone, clone_plan, diagnostic, require_arch


def label(text):
    return Gtk.Label(label=text, xalign=0, wrap=True, selectable=True)


def column():
    widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    for side in ("top", "bottom", "start", "end"):
        getattr(widget, "set_margin_" + side)(24)
    return widget


def describe(data):
    if "url" in data:
        return ("Cloner ce dépôt :\n" + data["url"] + "\n\nDestination :\n" + data["destination"]
                + "\n\nAucune configuration ne sera activée par le clonage.")
    if "records" in data:
        lines = ["Annuler le déploiement — état : " + data["state"],
                 "Les liens ci-dessous seront retirés et les fichiers sauvegardés restaurés."]
        for record in data["records"]:
            lines.append("\n" + record["target"] + ("\nRestaurer la sauvegarde."
                         if record["backup"] else "\nRetirer le lien créé."))
        return "\n".join(lines)
    lines = ["Configurations : " + ", ".join(data["packages"]),
             "Dépôt : " + data["repository"], "Cible : " + data["target"],
             "\nLes fichiers en conflit seront sauvegardés avant la création des liens."]
    labels = {"nouveau": "Créer le lien", "actif": "Déjà actif", "sauvegarder": "Sauvegarder puis créer le lien"}
    for item in data["entries"]:
        lines.append("\n" + labels[item["status"]] + "\n" + item["target"] + "\nSource : " + item["source"])
    return "\n".join(lines)


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Dotfilepilot")
        self.set_default_size(1050, 760)
        self.reviewed = None
        self.pending = None
        self.generation = 0
        self.busy = False
        header = Gtk.HeaderBar()
        header.set_title_widget(label("Dotfilepilot"))
        self.set_titlebar(header)
        stack = Gtk.Stack(hexpand=True, vexpand=True)
        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(stack)
        sidebar.set_size_request(200, -1)
        home = column()
        home.append(label("Gérer mes configurations"))
        home.append(label("1. Vérifiez les dépendances. 2. Clonez ou choisissez votre dépôt. "
                          "3. Sélectionnez les configurations. 4. Examinez les liens et sauvegardes avant d’appliquer."))
        home.append(label(json.dumps(diagnostic(), ensure_ascii=False, indent=2)))
        home.append(label("Installation des composants, avec aperçu et confirmation dans un terminal :\n"
                          "python3 -m dotfilepilot dependances --appliquer\n\n"
                          "Le gestionnaire de paquets demande ensuite votre accord sur sa transaction. "
                          "Les applications configurées (Ghostty, Zsh…) s’installent séparément."))
        stack.add_titled(home, "home", "Accueil et dépendances")
        repository = column()
        repository.append(label("Dépôt de dotfiles"))
        self.url = Gtk.Entry(placeholder_text="https://github.com/proprietaire/dotfiles.git")
        self.repo = Gtk.Entry(placeholder_text="Dossier du dépôt existant ou destination du clonage")
        self.repo.set_text(str(Path.home() / "dotfiles"))
        repository.append(self.url)
        repository.append(self.repo)
        self.button(repository, "Préparer le clonage", self.prepare_clone)
        self.button(repository, "Analyser ce dépôt existant", self.inventory)
        repository.append(label("Aucun script, sous-module ou programme du dépôt n’est exécuté. "
                                "Le clonage HTTPS public est pris en charge en premier."))
        stack.add_titled(repository, "repo", "Dépôt")
        configs = column()
        configs.append(label("Configurations — dossier personnel"))
        self.target = Gtk.Entry()
        self.target.set_text(str(Path.home()))
        configs.append(label("Dossier cible"))
        configs.append(self.target)
        self.choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        config_scroll = Gtk.ScrolledWindow(vexpand=True)
        config_scroll.set_child(self.choices)
        configs.append(config_scroll)
        self.checks = []
        self.button(configs, "Préparer l’activation des configurations cochées", self.prepare_activation)
        stack.add_titled(configs, "configs", "Configurations")
        history = column()
        history.append(label("Annuler un déploiement"))
        self.identifier = Gtk.Entry(placeholder_text="Identifiant du déploiement")
        history.append(self.identifier)
        self.history_text = label("Actualisez pour consulter l’historique local.")
        history.append(self.history_text)
        self.button(history, "Actualiser l’historique", self.refresh_history)
        self.button(history, "Préparer l’annulation", self.prepare_undo)
        history.append(label("L’annulation restaure les anciens fichiers et conserve les sauvegardes. "
                             "Un fichier remplacé depuis le déploiement bloque l’annulation."))
        stack.add_titled(history, "history", "Sauvegardes et annulation")
        review = column()
        review.append(label("Aperçu et confirmation"))
        self.output = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scroller.set_child(self.output)
        review.append(scroller)
        self.agree = Gtk.CheckButton(label="J’ai examiné cet aperçu et j’autorise cette opération.")
        review.append(self.agree)
        self.apply_button = self.button(review, "Appliquer l’aperçu", self.execute)
        self.apply_button.set_sensitive(False)
        stack.add_titled(review, "review", "Aperçu")
        self.stack = stack
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.append(sidebar)
        body.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        body.append(stack)
        self.set_child(body)
        self.connect("close-request", self.closing)
        for field in (self.url, self.repo, self.target, self.identifier):
            field.connect("changed", self.invalidate)

    def button(self, parent, title, callback):
        button = Gtk.Button(label=title)
        button.connect("clicked", callback)
        parent.append(button)
        return button

    def invalidate(self, *_args):
        self.generation += 1
        self.pending = None
        self.agree.set_active(False)
        self.apply_button.set_sensitive(False)

    def closing(self, *_args):
        # Keep the process alive while a deployment or clone is being written.
        return self.busy

    def task(self, work, complete):
        if self.busy:
            return
        self.busy = True
        self.invalidate()
        generation = self.generation
        self.stack.set_visible_child_name("review")
        self.output.get_buffer().set_text("Opération en cours…")

        def finished(result, error):
            self.busy = False
            if generation != self.generation:
                self.output.get_buffer().set_text("Les champs ont changé. Recommencez l’aperçu.")
                return False
            if error:
                self.output.get_buffer().set_text(str(error))
            else:
                complete(result)
            return False

        def worker():
            try:
                result = work()
                GLib.idle_add(finished, result, None)
            except Exception as error:
                GLib.idle_add(finished, None, error)
        Thread(target=worker, daemon=False).start()

    def review(self, data, action):
        self.output.get_buffer().set_text(describe(data))
        self.pending = action
        self.apply_button.set_sensitive(True)

    def prepare_clone(self, *_args):
        url, repo = self.url.get_text(), self.repo.get_text()
        self.task(lambda: clone_plan(url, repo),
                  lambda plan: self.review(plan, lambda: clone(plan)))

    def inventory(self, *_args):
        repo = self.repo.get_text()

        def done(names):
            for check in self.checks:
                self.choices.remove(check)
            self.checks = []
            for name in names:
                check = Gtk.CheckButton(label=name)
                check.connect("toggled", self.invalidate)
                self.checks.append(check)
                self.choices.append(check)
            self.stack.set_visible_child_name("configs")
        self.task(lambda: deploy.packages(repo), done)

    def prepare_activation(self, *_args):
        repo, target = self.repo.get_text(), self.target.get_text()
        names = [check.get_label() for check in self.checks if check.get_active()]
        self.task(lambda: deploy.preview(repo, target, names),
                  lambda plan: self.review(plan, lambda: deploy.apply(plan)))

    def refresh_history(self, *_args):
        self.task(deploy.history, lambda names: self.show_history(names))

    def show_history(self, names):
        self.history_text.set_text("\n".join(names) or "Aucun déploiement.")
        self.stack.set_visible_child_name("history")

    def prepare_undo(self, *_args):
        identifier = self.identifier.get_text()
        self.task(lambda: deploy.preview_undo(identifier),
                  lambda plan: self.review(plan, lambda: deploy.undo(identifier, plan)))

    def execute(self, *_args):
        if not self.pending or not self.agree.get_active() or self.busy:
            return
        action = self.pending

        def work():
            require_arch()
            return action()
        self.task(work, lambda message: self.output.get_buffer().set_text(str(message)))


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.dotfilepilot.App",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        if not self.get_active_window():
            Window(self)
        self.get_active_window().present()
