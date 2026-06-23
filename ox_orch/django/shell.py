from django.core.management import call_command


from ox_orch.core.shell import Shell


__all__ = ("ManageCommandShell",)


class ManageCommandShell(Shell):
    """
    Invoke a Django manage command from within the Django project.
    You MUST ensure Django initialization (eventually by spawning it into a DjangoProjectOperation.
    """

    def run(self, command, check=False):
        if isinstance(command, list):
            call_command(*command)
        else:
            call_command(command)

    def python_cmd(self, *args):
        return ["shell", "-c", " ".join(*args)]

    def python_module(self, *args):
        raise NotImplementedError("You can invoke python module with ManageCommand shell")
