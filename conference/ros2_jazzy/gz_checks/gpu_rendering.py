"""Record the renderer used by the actual headless Ogre2 server."""

import re
import shutil

GL_FIELDS = re.compile(r'\b(GL_VENDOR|GL_RENDERER)[ \t]*[:=][ \t]*([^\r\n]+)', re.IGNORECASE)


def save_renderer(server_home, raw):
    # gz-rendering writes a new Ogre log under HOME for each server.
    ogre_log = server_home/'.gz/rendering/ogre2.log'
    result = dict(renderer=None, ogre_log=None, gl_vendor=None, gl_renderer=None, gpu_rendered=None)
    if not ogre_log.is_file():
        return result
    shutil.copyfile(ogre_log, raw/'ogre2.log')
    result['ogre_log'] = 'ogre2.log'
    text = (raw/'ogre2.log').read_text(errors='replace')
    for key, value in GL_FIELDS.findall(text):
        key = key.lower()
        if key == 'gl_vendor' or result[key] is not None:
            # Ogre2 logs GL_VENDOR followed by GL_RENDERER for each context.
            result.update(gl_vendor=None, gl_renderer=None)
        result[key] = value.strip() or None
    names = re.findall(r'\bDevice Name[ \t]*[:=][ \t]*([^\r\n]+)', text, re.IGNORECASE)
    result['renderer'] = result['gl_renderer'] or (names[-1].strip() if names else None)
    vendor = (result['gl_vendor'] or '').casefold()
    renderer = (result['gl_renderer'] or '').casefold()
    if 'mesa' in vendor or any(name in renderer for name in ('llvmpipe', 'softpipe', 'swrast')):
        result['gpu_rendered'] = False
    elif 'nvidia' in vendor and renderer:
        result['gpu_rendered'] = True
    return result
