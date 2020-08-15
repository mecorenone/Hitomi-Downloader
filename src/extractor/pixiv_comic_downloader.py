# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: pixiv_comic_downloader.pyo
# Compiled at: 2019-10-03 10:20:37
import downloader, requests
from utils import Soup, urljoin, Session, LazyUrl, Downloader, try_n, get_imgs_already
import ree as re, json, os
from fucking_encoding import clean_title
from translator import tr_
from timee import sleep
import page_selector, phantomjs, clf2
from hashlib import md5
from datetime import datetime
SALT = 'mAtW1X8SzGS880fsjEXlM73QpS1i4kUMBhyhdaYySk8nWz533nrEunaSplg63fzT'


class Image(object):

    def __init__(self, url, page, p):
        ext = os.path.splitext(url.split('?')[0])[1]
        self.filename = (u'{}/{:04}{}').format(page.title, p, ext)

        def f(_):
            return url

        self.url = LazyUrl(page.url, f, self)


class Page(object):

    def __init__(self, url, title):
        self.title = clean_title(title)
        self.url = url


@Downloader.register
class Downloader_pixiv_comic(Downloader):
    type = 'pixiv_comic'
    URLS = ['comic.pixiv.net/works', 'comic.pixiv.net/viewer/']
    _soup = None

    def init(self):
        self.url = self.url.replace('pixiv_comic_', '')
        if '/viewer/' in self.url:
            html = downloader.read_html(self.url)
            id = re.find('/works/([0-9]+)', html)
            self.url = ('https://comic.pixiv.net/works/{}').format(id)
            self.customWidget.print_(('fix url: {}').format(self.url))

    @property
    def id(self):
        return self.url

    @property
    def soup(self):
        if self._soup is None:
            self.session = Session()
            self._soup = get_soup(self.url, session=self.session, cw=self.customWidget)
        return self._soup

    @property
    def name(self):
        soup = self.soup
        title = soup.find('meta', {'property': 'og:title'}).attrs['content']
        artist = get_artist(soup)
        if artist:
            self.customWidget.artist = artist
        else:
            artist = 'N/A'
        self.dirFormat = self.dirFormat.replace('0:id', '').replace('id', '').replace('()', '').replace('[]', '').strip()
        self.customWidget.print_((u'dirFormat: {}').format(self.dirFormat))
        title = self.format_title('N/A', 'id', title, artist, 'N/A', 'N/A', 'Japanese')
        while '  ' in title:
            title = title.replace('  ', ' ')

        return title

    def read(self):
        name = self.name
        self.imgs = get_imgs(self.url, name, self.soup, self.session, cw=self.customWidget)
        for img in self.imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = name


def get_soup(url, session=None, cw=None):
    html = read_html(url, session=session, cw=cw)
    soup = Soup(html)
    return soup


def read_html(url, session=None, cw=None):
    r = clf2.solve(url, session=session, cw=cw)
    html = r['html']

    return html


def get_artist(soup):
    return soup.find('div', class_='works-author').text.strip()


def get_pages(soup, url):
    main = soup.find('div', class_='work-main-column')
    view = main.find('div', class_='two-works')
    pages = []
    for a in view.findAll('a', class_='episode-list-item'):
        href = a.attrs['href']
        href = urljoin(url, href)
        number = a.find('div', class_='episode-num').text.strip()
        title = a.find('div', class_='episode-title').text.strip()
        title = (u' - ').join(x for x in [number, title] if x)
        page = Page(href, title)
        pages.append(page)

    return pages[::-1]


@page_selector.register('pixiv_comic')
@try_n(4)
def f(url):
    if '/viewer/' in url:
        html = read_html(url)
        id = re.find('/works/([0-9]+)', html)
        url = ('https://comic.pixiv.net/works/{}').format(id)
    html = read_html(url)
    soup = Soup(html)
    pages = get_pages(soup, url)
    return pages


def get_imgs(url, title, soup=None, session=None, cw=None):
    if soup is None:
        soup = get_soup(url, cw=cw)
    if session is None:
        session = Session()
        html = read_html(url, session=session)
    pages = get_pages(soup, url)
    pages = page_selector.filter(pages, cw)
    imgs = []
    for i, page in enumerate(pages):
        imgs_already = get_imgs_already('pixiv_comic', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue
        if cw is not None:
            if not cw.alive:
                return
            cw.setTitle((u'{} {} / {}  ({} / {})').format(tr_(u'\uc77d\ub294 \uc911...'), title, page.title, i + 1, len(pages)))
        imgs += get_imgs_page(page, session)

    return imgs


@try_n(4)
def get_imgs_page(page, session):
    id = re.find('/viewer/.+?/([0-9]+)', page.url)
    url_api = 'https://comic.pixiv.net/api/app/episodes/{}/read'.format(id)
    local_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')
    headers = {
        'X-Client-Time': local_time,
        'X-Client-Hash': md5((local_time + SALT).encode('utf8')).hexdigest(),
        'X-Requested-With': 'pixivcomic',
        'referer': page.url,
        }
    r = session.get(url_api, headers=headers)
    r.raise_for_status()
    data_raw = r.text
    data = json.loads(data_raw)
    pages = data['data']['reading_episode']['pages']

    if not pages:
        raise Exception('No pages')
    
    imgs = []
    for p in pages:
        img = p['url']
        img = img.replace('webp%3Ajpeg', 'jpeg')
        img = Image(img, page, len(imgs))
        imgs.append(img)

    return imgs

