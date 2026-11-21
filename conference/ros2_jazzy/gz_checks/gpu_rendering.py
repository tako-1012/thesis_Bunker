"""Record the renderer used by the actual headless Ogre2 server."""

import re
import shutil


def save_renderer(server_home, raw):
    # gz-rendering writes a new Ogre log under HOME for each server.
    ogre_log = server_home/'.gz/rendering/ogre2.log'
    result = dict(renderer=None, ogre_log=None)
    if not ogre_log.is_file():
        return result
    shutil.copyfile(ogre_log, raw/'ogre2.log')
    result['ogre_log'] = 'ogre2.log'
    text = ogre_log.read_text(errors='replace')
    for key in (r'\bGL_RENDERER', r'\bDevice Name'):
        names = re.findall(key+r'[ \t]*[:=][ \t]*([^\r\n]+)', text, re.IGNORECASE)
        if names:
            result['renderer'] = names[-1].strip()
            break
    return result
