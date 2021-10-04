import asyncio
import logging
import os

from aiohttp import web
import aiofiles


try:
    LOGGING_LEVEL = logging._nameToLevel[os.getenv('DOWNLOAD_SERVICE_LOGGING_LEVEL')]
except KeyError:
    LOGGING_LEVEL = logging.INFO

try:
    PAUSE = float(os.getenv('DOWNLOAD_SERVICE_PAUSE'))
except (ValueError, TypeError):
    PAUSE = None

PHOTO_PATH = os.getenv('DOWNLOAD_SERVICE_PATH', 'test_photos2')


logging.basicConfig(level=LOGGING_LEVEL)


async def archivate(request):
    response = web.StreamResponse()

    archive_hash = request.match_info['archive_hash']

    cwd = os.getcwd()
    dirname = os.path.join(PHOTO_PATH, archive_hash)

    if not os.path.exists(dirname):
        raise web.HTTPNotFound(body='Архив не существует или был удален'.encode('utf-8'))

    process = await asyncio.create_subprocess_exec(
        '/usr/bin/zip', '-r', '-', archive_hash,
        stdout=asyncio.subprocess.PIPE,
        cwd=PHOTO_PATH
    )

    response.headers['Content-Disposition'] = f'attachment; filename="{archive_hash}.zip"'

    logging.debug('Sending response headers ...')
    await response.prepare(request)

    try:
        logging.info('Archive sending started ...')
        while True:
            buf = await process.stdout.read(4096)
            if not buf:
                break

            logging.debug('Sending archive chunk ...')
            await response.write(buf)
            if PAUSE:
                await asyncio.sleep(PAUSE)
            
    except (asyncio.CancelledError, ConnectionResetError):
        logging.info('Download was interrupted by user')
        raise
    except Exception as e:
        logging.error(f'Internal server error: {e}')
    finally:
        if process.returncode is None:
            process.kill()
            process.communicate()

    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archivate),
    ])
    web.run_app(app)
