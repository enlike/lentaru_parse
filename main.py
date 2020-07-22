# coding=utf-8
import logging
import os
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from requests import get

from markdown import markdownify as md

logger = logging.getLogger(__name__)


def ask_for_site_url():
    try:
        url = str(input('Enter Lenta.ru (news/article) ref: '))
        scheme, host, path, params, query, fragment = urlparse(url)
        if host != 'lenta.ru':
            print('Must be Lenta.ru link')
            return ask_for_site_url()
        return url
    except ValueError:
        print('Must be Lenta.ru link')
        return ask_for_site_url()


def get_current_path():
    return os.path.abspath(os.getcwd())


def replace_symbols(filename: str) -> str:
    """
        To save on Windows.
        Replaces forbidden symbols from replace_em to underscore (_)
    """
    replace_em = ['\\', '/', ' ', ':', '*', '?', '<', '>', '|', '"', '.']
    for symbol in replace_em:
        filename = filename.replace(symbol, '_') if symbol in filename else filename
    return filename


class Parser:
    def __init__(self, url):
        self.url = url
        self.news_type = None
        self.scheme, self.host, self.path, self.params, self.query, self.fragment = urlparse(self.url)

    @property
    def base_url(self):
        return f'{self.scheme}://{self.host}'

    def get_url_data(self):
        """rec_path - task1"""
        data = get(self.url)
        if data:
            rec_path = os.path.join('\\'.join([i for i in data.request.path_url.split('/') if i]))
            self.news_type = data.request.path_url.split('/')[--1]
            soup = BeautifulSoup(data.text)
            _html = soup.find('div', {'class': f'b-topic b-topic_{self.news_type}'}) if self.path.startswith(
                '/news') else soup.find('article')
            _html = self.rm_unnecessary_attrs(_html)
            self.save_output(rec_path, _html)
        else:
            logger.info('No data received')

    @staticmethod
    def rm_unnecessary_attrs(_html):
        to_delete_attrs = ['script', 'style', 'section']
        for i in to_delete_attrs:
            [x.extract() for x in _html.find_all(i)]
        [x.extract() for x in _html.find_all('aside', {'class': 'b-inline-topics-box'})]
        [x.extract() for x in _html.find_all('div', {'class': 'b-socials'})]
        return _html

    def save_output(self, *args):
        path_url, _html = args
        file_name = f'{replace_symbols(path_url).rstrip("_")}.md'
        save_path = os.path.join(get_current_path(), 'output', path_url)
        full_file_path = os.path.join(save_path, file_name)
        if not os.path.exists(save_path):
            os.makedirs(save_path, exist_ok=True)
        with open(full_file_path, 'w', encoding='utf-8') as output:
            output.write(md(_html, base_url=self.base_url))
        logger.info(f'file: {full_file_path}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)-15s %(name)-5s %(relativeCreated)5d %(levelname)-8s %(message)s')
    site_url = ask_for_site_url()
    p = Parser(site_url).get_url_data()
