"""GTK est chargé à la demande, le terminal reste autonome."""


def launch():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from .gtk_app import Application
    except (ImportError, ValueError) as error:
        print("GTK4 / PyGObject indisponible : " + str(error))
        print("Sur Arch Linux et ses dérivées : lancer d’abord python3 -m dotfilepilot dependances --appliquer")
        return 3
    return Application().run([])
