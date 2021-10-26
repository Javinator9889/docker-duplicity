#                             Jinja utils
#                  Copyright (C) 2021 - Javinator9889
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#                   (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#               GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
"""Package that contains all Jinja-related utilities and packages"""
from jinja2 import Environment, FileSystemLoader


class Jinja:
    __instance__ = None

    # This is a singleton class, which means that it's created
    # only the first time
    def __new__(cls):
        if Jinja.__instance__ is None:
            instance = object.__new__(cls)
            instance.__must_init__ = True
            Jinja.__instance__ = instance
        return Jinja.__instance__

    def __init__(self):
        # First time this class has been created
        if self.__must_init__:
            loader = FileSystemLoader(r"/usr/local/share/templates")
            self.env = Environment(
                auto_reload=False,
                cache_size=10,
                loader=loader,
                trim_blocks=True,
            )

    def render(self, template: str, data: dict[str, object]) -> str:
        tmpl = self.env.get_template(template)
        return tmpl.render(data)
