"""Fenêtre GTK4 native et opérations hors du fil d’interface."""

import json
from pathlib import Path
from threading import Thread

from gi.repository import Gio, GLib, GObject, Gtk, Pango

from . import deployments as deploy
from .presentation import activation_table, current_state_text, repository_status_text
from .monitoring import current_state
from .git_status import repository_status
from .system import clone, clone_plan, diagnostic, require_supported


APP_ID = "io.github.dotfilepilot.App"


def label(text):
    return Gtk.Label(label=text, xalign=0, wrap=True, selectable=True)


def column():
    widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    for side in ("top", "bottom", "start", "end"):
        getattr(widget, "set_margin_" + side)(24)
    return widget


class PreviewRow(GObject.Object):
    """Lightweight model item; cell widgets are created and reused by ColumnView."""

    def __init__(self, package, entry):
        super().__init__()
        self.package = package
        self.action = entry["action"]
        self.source = entry["source"]
        self.target = entry["target"]


def setup_preview_cell(_factory, item):
    cell = label("")
    cell.set_valign(Gtk.Align.START)
    cell.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    cell.set_max_width_chars(40)
    for side in ("top", "bottom", "start", "end"):
        getattr(cell, "set_margin_" + side)(6)
    item.set_child(cell)


def bind_preview_cell(_factory, item, field):
    item.get_child().set_text(getattr(item.get_item(), field))


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
        icon_path = str(Path(__file__).parent / "assets/icons")
        theme = Gtk.IconTheme.get_for_display(self.get_display())
        if icon_path not in theme.get_search_path():
            theme.add_search_path(icon_path)
        self.set_icon_name(APP_ID)
        self.set_default_size(1050, 760)
        self.reviewed = None
        self.pending = None
        self.generation = 0
        self.busy = False
        self.preview_generation = 0
        self.preview_running = False
        self.preview_next = None
        self.preview_installing = None
        self.preview_action = None
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
        self.button(repository, "Consulter l’état Git local", self.refresh_repository_status)
        self.git_output = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.git_output.get_buffer().set_text("Aucune observation Git effectuée.")
        git_scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        git_scroll.set_child(self.git_output)
        repository.append(git_scroll)
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
        self.history_entries = []
        self.history_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.history_list.connect("row-selected", self.select_history)
        history_scroll = Gtk.ScrolledWindow(vexpand=True)
        history_scroll.set_child(self.history_list)
        history.append(history_scroll)
        history.append(label("Sélectionnez un déploiement ou saisissez son identifiant."))
        self.identifier = Gtk.Entry(placeholder_text="Identifiant du déploiement")
        history.append(self.identifier)
        self.history_text = label("Actualisez pour consulter l’historique local.")
        history.append(self.history_text)
        self.button(history, "Actualiser l’historique", self.refresh_history)
        self.undo_button = self.button(history, "Préparer l’annulation", self.prepare_undo)
        self.undo_button.set_sensitive(False)
        history.append(label("L’annulation restaure les anciens fichiers et conserve les sauvegardes. "
                             "Un fichier remplacé depuis le déploiement bloque l’annulation."))
        stack.add_titled(history, "history", "Sauvegardes et annulation")
        status_page = column()
        status_page.append(label("État actuel des liens journalisés"))
        status_page.append(label("Actualisez pour observer les liens connus de Dotfilepilot. "
                                 "Cette vue ne répare ni ne modifie les configurations."))
        self.button(status_page, "Actualiser l’état", self.refresh_current_state)
        self.status_output = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.status_output.get_buffer().set_text("Aucune observation effectuée. Cliquez sur Actualiser l’état.")
        status_scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        status_scroll.set_child(self.status_output)
        status_page.append(status_scroll)
        stack.add_titled(status_page, "status", "État actuel")
        review = column()
        review.append(label("Aperçu et confirmation"))
        self.output = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.output_scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.output_scroll.set_child(self.output)
        review.append(self.output_scroll)
        self.activation_plan = None
        self.activation_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, vexpand=True)
        self.activation_context = label("")
        self.activation_summary = label("")
        self.activation_panel.append(self.activation_context)
        self.activation_panel.append(self.activation_summary)
        filters = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        filters.append(label("Afficher"))
        self.preview_filter = Gtk.DropDown.new_from_strings(
            ["Tous les fichiers", "Nouveaux liens", "Déjà actifs", "Conflits à sauvegarder"])
        self.preview_filter_handler = self.preview_filter.connect("notify::selected", self.filter_preview)
        filters.append(self.preview_filter)
        self.activation_panel.append(filters)
        self.activation_panel.append(label("Le filtre limite uniquement l’affichage. "
                                           "L’activation concerne tous les fichiers de l’aperçu."))
        self.preview_visible = label("")
        self.activation_panel.append(self.preview_visible)
        self.preview_model = Gio.ListStore.new(PreviewRow)
        self.preview_table = Gtk.ColumnView.new(Gtk.NoSelection.new(self.preview_model))
        self.preview_table.set_hexpand(True)
        for title, field, width in (("Configuration", "package", 140), ("Action", "action", 180),
                                    ("Source", "source", 260), ("Destination", "target", 260)):
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", setup_preview_cell)
            factory.connect("bind", bind_preview_cell, field)
            table_column = Gtk.ColumnViewColumn.new(title, factory)
            table_column.set_resizable(True)
            table_column.set_fixed_width(width)
            table_column.set_expand(field in ("source", "target"))
            self.preview_table.append_column(table_column)
        table_scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        table_scroll.set_child(self.preview_table)
        self.activation_panel.append(table_scroll)
        self.activation_panel.set_visible(False)
        review.append(self.activation_panel)
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
        self.identifier.connect("changed", self.identifier_changed)

    def button(self, parent, title, callback):
        button = Gtk.Button(label=title)
        button.connect("clicked", callback)
        parent.append(button)
        return button

    def invalidate(self, *_args):
        self.generation += 1
        self.preview_generation += 1
        self.preview_next = None
        self.preview_installing = None
        self.preview_action = None
        self.pending = None
        self.agree.set_active(False)
        self.agree.set_sensitive(False)
        self.apply_button.set_sensitive(False)

    def closing(self, *_args):
        # Keep the process alive while a deployment or clone is being written.
        return self.busy or self.preview_running or self.preview_installing is not None

    def task(self, work, complete, intervention=False):
        if self.busy:
            return
        self.busy = True
        self.invalidate()
        self.activation_plan = None
        self.preview_model.remove_all()
        self.activation_panel.set_visible(False)
        self.output_scroll.set_visible(True)
        generation = self.generation
        self.stack.set_visible_child_name("review")
        self.output.get_buffer().set_text("Opération en cours…")

        def finished(result, error):
            self.busy = False
            if generation != self.generation and not intervention:
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
        self.invalidate()
        self.activation_plan = data if "entries" in data else None
        self.output.get_buffer().set_text("" if self.activation_plan is not None else describe(data))
        self.activation_panel.set_visible(self.activation_plan is not None)
        self.output_scroll.set_visible(self.activation_plan is None)
        if self.activation_plan is not None:
            self.preview_action = action
            self.activation_summary.set_text("")
            self.activation_context.set_text("Configurations : " + ", ".join(data["packages"])
                                             + "\nDépôt : " + data["repository"] + "\nCible : " + data["target"])
            self.preview_filter.handler_block(self.preview_filter_handler)
            try:
                self.preview_filter.set_selected(0)
            finally:
                self.preview_filter.handler_unblock(self.preview_filter_handler)
            self.render_activation()
        else:
            self.preview_model.remove_all()
            self.pending = action
            self.agree.set_sensitive(True)
            self.apply_button.set_sensitive(True)

    def filter_preview(self, *_args):
        # Filtering never changes the operation, but its confirmation is revoked.
        self.agree.set_active(False)
        if self.activation_plan is not None and self.preview_action is not None:
            self.render_activation()

    def render_activation(self):
        """Keep only the latest requested filter while one preparation is running."""
        statuses = (None, "nouveau", "actif", "sauvegarder")
        self.preview_generation += 1
        self.pending = None
        self.agree.set_active(False)
        self.agree.set_sensitive(False)
        self.apply_button.set_sensitive(False)
        self.preview_installing = None
        self.preview_model.remove_all()
        self.preview_visible.set_text("Préparation de l’affichage…")
        self.preview_next = (self.preview_generation, self.generation, self.activation_plan,
                             statuses[self.preview_filter.get_selected()], self.preview_action)
        self.start_preview_request()

    def preview_is_current(self, request):
        token, generation, plan, _status, action = request
        return (token == self.preview_generation and generation == self.generation
                and plan is self.activation_plan and action is self.preview_action and not self.busy)

    def start_preview_request(self):
        if self.preview_running or self.preview_next is None:
            return
        request = self.preview_next
        self.preview_next = None
        self.preview_running = True

        def finished(view, error):
            self.preview_running = False
            if self.preview_is_current(request):
                if error:
                    self.preview_visible.set_text("Affichage impossible : " + str(error))
                else:
                    self.install_activation(view, request)
            self.start_preview_request()
            return False

        def worker():
            try:
                view = activation_table(request[2], request[3])
                GLib.idle_add(finished, view, None)
            except Exception as error:
                GLib.idle_add(finished, None, error)
        Thread(target=worker, daemon=False).start()

    def install_activation(self, view, request):
        """Create GObjects only on the GTK thread, in bounded idle batches."""
        counts = view["counts"]
        self.activation_summary.set_text(
            f"Total : {view['total']} fichier(s) — {counts['nouveau']} nouveau(x) lien(s), "
            f"{counts['actif']} déjà actif(s), {counts['sauvegarder']} conflit(s) à sauvegarder.\n"
            f"Liens à créer : {counts['nouveau'] + counts['sauvegarder']} ; "
            f"sauvegardes prévues : {counts['sauvegarder']}.")
        self.preview_installing = request[0]
        position = 0

        def install_batch():
            nonlocal position
            if not self.preview_is_current(request):
                if self.preview_installing == request[0]:
                    self.preview_installing = None
                return False
            try:
                batch = [PreviewRow(package, entry) for package, entry in view["rows"][position:position + 200]]
                self.preview_model.splice(self.preview_model.get_n_items(), 0, batch)
            except Exception as error:
                self.preview_installing = None
                self.preview_model.remove_all()
                self.preview_visible.set_text("Chargement impossible : " + str(error))
                return False
            position += len(batch)
            if position < len(view["rows"]):
                self.preview_visible.set_text(f"Chargement : {position} sur {view['visible']} fichier(s)…")
                return True
            self.preview_installing = None
            self.preview_visible.set_text(f"{view['visible']} fichier(s) affiché(s) sur {view['total']}."
                                         if view["visible"] else "Aucun fichier ne correspond à ce filtre.")
            self.pending = request[4]
            self.agree.set_active(False)
            self.agree.set_sensitive(True)
            self.apply_button.set_sensitive(True)
            return False

        GLib.idle_add(install_batch)

    def prepare_clone(self, *_args):
        url, repo = self.url.get_text(), self.repo.get_text()
        self.task(lambda: clone_plan(url, repo),
                  lambda plan: self.review(plan, lambda: clone(plan)))

    def refresh_repository_status(self, *_args):
        repository = self.repo.get_text()
        self.task(lambda: repository_status(repository), self.show_repository_status)

    def show_repository_status(self, report):
        self.git_output.get_buffer().set_text(repository_status_text(report))
        self.stack.set_visible_child_name("repo")

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
        self.task(deploy.history_details, self.show_history)

    def refresh_current_state(self, *_args):
        self.task(current_state, self.show_current_state)

    def show_current_state(self, report):
        self.status_output.get_buffer().set_text(current_state_text(report))
        self.stack.set_visible_child_name("status")

    def show_history(self, entries):
        self.invalidate()
        self.history_entries = entries
        while self.history_list.get_first_child():
            self.history_list.remove(self.history_list.get_first_child())
        self.identifier.set_text("")
        states = {"preparation": "Préparation", "application": "Application en cours",
                  "actif": "Actif", "interrompu": "Interrompu", "annule": "Annulé"}
        for entry in entries:
            row = Gtk.ListBoxRow()
            row.identifier = entry["identifier"]
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            for side in ("top", "bottom", "start", "end"):
                getattr(content, "set_margin_" + side)(12)
            if entry["error"]:
                content.append(label("Journal indisponible — " + entry["identifier"]))
                content.append(label(entry["error"]))
            else:
                content.append(label(entry["date"] + " — " + states[entry["state"]]))
                content.append(label("Dépôt : " + entry["repository"]))
                content.append(label("Configurations : " + ", ".join(entry["packages"])))
                content.append(label("Cible : " + entry["target"]))
                content.append(label("Identifiant : " + entry["identifier"]))
            row.set_child(content)
            self.history_list.append(row)
        self.history_text.set_text("Sélectionnez un déploiement pour préparer son annulation."
                                   if entries else "Aucun déploiement.")
        self.identifier_changed()
        self.stack.set_visible_child_name("history")

    def select_history(self, _list, row):
        self.invalidate()
        if row is not None:
            self.identifier.set_text(row.identifier)
        self.identifier_changed()

    def identifier_changed(self, *_args):
        identifier = self.identifier.get_text()
        row = self.history_list.get_selected_row()
        if row is not None and row.identifier != identifier:
            self.history_list.unselect_all()
        entry = next((item for item in self.history_entries if item["identifier"] == identifier), None)
        eligible = bool(identifier) and (entry is None or (not entry["error"] and entry["state"] != "annule"))
        self.undo_button.set_sensitive(eligible)

    def prepare_undo(self, *_args):
        identifier = self.identifier.get_text()
        self.task(lambda: deploy.preview_undo(identifier),
                  lambda plan: self.review(plan, lambda: deploy.undo(identifier, plan)))

    def execute(self, *_args):
        if not self.pending or not self.agree.get_active() or self.busy:
            return
        action = self.pending

        def work():
            require_supported()
            return action()
        self.task(work, lambda message: self.output.get_buffer().set_text(str(message)),
                  intervention=True)


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        if not self.get_active_window():
            Window(self)
        self.get_active_window().present()
