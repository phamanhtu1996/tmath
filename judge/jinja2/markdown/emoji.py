import re

import mistune

from django.conf import settings

class EmojiInlineGrammar(mistune.InlineGrammar):
  emoji = re.compile(r'^\:([+\-\w]+)\:', re.DOTALL)


class EmojiInlineLexer(mistune.InlineLexer):
    grammar_class = EmojiInlineGrammar

    def __init__(self, *args, **kwargs):
        self.default_rules.insert(self.default_rules.index('strikethrough') + 1, 'emoji')
        super().__init__(*args, **kwargs)

    def output_emoji(self, m):
      return self.renderer.emoji(m.group(1))


class EmojiRenderer(mistune.Renderer):

    def emoji(self, emoji):
      url = '{0}{1}.png'.format(
        settings.MARTOR_MARKDOWN_BASE_EMOJI_URL, emoji
      )
      return "<img src='%s' class='marked-emoji'>" % url
