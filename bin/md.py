#                               Markdown
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
"""Contains Markdown-related functions, variables and more"""
import mistune
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import html


class HighlightRenderer(mistune.Renderer):
    def block_code(self, code, lang=None):
        if lang is None:
            return f"\n<pre><code>{mistune.escape(code)}</code></pre>\n"
        lexer = get_lexer_by_name(lang, stripall=False)
        formatter = html.HtmlFormatter()
        return highlight(code, lexer, formatter)
