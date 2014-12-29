#!/usr/bin/env python

from bs4 import BeautifulSoup
from xml.dom import minidom
from urllib2 import urlopen
import urllib2
from string import maketrans, punctuation
from operator import itemgetter
from re import sub, match
from nltk import stem
from json import loads
import re
import sys
import nltk

wordcount = {}
pages_crawled = []
pages_to_crawl = []
stem_to_word = {}
stemmer = stem.porter.PorterStemmer()
#stemmer = stem.lancaster.LancasterStemmer()

# This list of English stop words is taken from the "Glasgow Information
# Retrieval Group". The original list can be found at
# http://ir.dcs.gla.ac.uk/resources/linguistic_utils/stop_words
ENGLISH_STOP_WORDS = frozenset([
    "a", "about", "above", "across", "after", "afterwards", "again", "against",
    "all", "almost", "alone", "along", "already", "also", "although", "always",
    "am", "among", "amongst", "amoungst", "amount", "an", "and", "another",
    "any", "anyhow", "anyone", "anything", "anyway", "anywhere", "are",
    "around", "as", "at", "back", "be", "became", "because", "become",
    "becomes", "becoming", "been", "before", "beforehand", "behind", "being",
    "below", "beside", "besides", "between", "beyond", "bill", "both",
    "bottom", "but", "by", "call", "can", "cannot", "cant", "co", "con",
    "could", "couldnt", "cry", "de", "describe", "detail", "do", "done",
    "down", "due", "during", "each", "eg", "eight", "either", "eleven", "else",
    "elsewhere", "empty", "enough", "etc", "even", "ever", "every", "everyone",
    "everything", "everywhere", "except", "few", "fifteen", "fify", "fill",
    "find", "fire", "first", "five", "for", "former", "formerly", "forty",
    "found", "four", "from", "front", "full", "further", "get", "give", "go",
    "had", "has", "hasnt", "have", "he", "hence", "her", "here", "hereafter",
    "hereby", "herein", "hereupon", "hers", "herself", "him", "himself", "his",
    "how", "however", "hundred", "i", "ie", "if", "in", "inc", "indeed",
    "interest", "into", "is", "it", "its", "itself", "keep", "last", "latter",
    "latterly", "least", "less", "ltd", "made", "many", "may", "me",
    "meanwhile", "might", "mill", "mine", "more", "moreover", "most", "mostly",
    "move", "much", "must", "my", "myself", "name", "namely", "neither",
    "never", "nevertheless", "next", "nine", "no", "nobody", "none", "noone",
    "nor", "not", "nothing", "now", "nowhere", "of", "off", "often", "on",
    "once", "one", "only", "onto", "or", "other", "others", "otherwise", "our",
    "ours", "ourselves", "out", "over", "own", "part", "per", "perhaps",
    "please", "put", "rather", "re", "same", "see", "seem", "seemed",
    "seeming", "seems", "serious", "several", "she", "should", "show", "side",
    "since", "sincere", "six", "sixty", "so", "some", "somehow", "someone",
    "something", "sometime", "sometimes", "somewhere", "still", "such",
    "system", "take", "ten", "than", "that", "the", "their", "them",
    "themselves", "then", "thence", "there", "thereafter", "thereby",
    "therefore", "therein", "thereupon", "these", "they",
    "third", "this", "those", "though", "three", "through", "throughout",
    "thru", "thus", "to", "together", "too", "top", "toward", "towards",
    "twelve", "twenty", "two", "un", "under", "until", "up", "upon", "us",
    "very", "via", "was", "we", "well", "were", "what", "whatever", "when",
    "whence", "whenever", "where", "whereafter", "whereas", "whereby",
    "wherein", "whereupon", "wherever", "whether", "which", "while", "whither",
    "who", "whoever", "whole", "whom", "whose", "why", "will", "with",
    "within", "without", "would", "yet", "you", "your", "yours", "yourself",
    "yourselves"])

TOKEN_REGEX = re.compile(r'(?u)\b\w\w+\b')

class Page(object):
    """
    Container for each page and the analyzer.
    """

    def __init__(self, url='', site=''):
        """
        Variables go here, *not* outside of __init__
        """
        self.site = site
        self.url = url
        self.title = u''
        self.description = u''
        self.keywords = u''
        self.warnings = []
        self.translation = maketrans(punctuation, str(u' ' * len(punctuation)).encode('utf-8'))
        super(Page, self).__init__()

    def talk(self, output='all'):
        """
        Print the results to stdout, tab delimited
        """
        if output == 'all':
            print "{0}\t{1}\t{2}\t{3}\t{4}".format(self.url, self.title, self.description, self.keywords, self.warnings)
        elif output == 'warnings':
            if len(self.warnings) > 0:
                print "{0}\t{1}".format(self.url, self.warnings)
        else:
            print "I don't know what {0} is.".format(output)

    def populate(self, bs):
        """
        Populates the instance variables from BeautifulSoup
        """
        self.title = bs.title.text

        descr = bs.findAll('meta', attrs={'name':'description'})

        if len(descr) > 0:
            self.description = descr[0].get('content')

        keywords = bs.findAll('meta', attrs={'name':'keywords'})

        if len(keywords) > 0:
            self.keywords = keywords[0].get('content')

    def analyze(self):
        """
        Analyze the page and populate the warnings list
        """
        if self.url in pages_crawled:
            return

        pages_crawled.append(self.url)

        try:
            page = urlopen(self.url)
        except urllib2.HTTPError:
            self.warn('Returned 404')
            return

        encoding = page.headers['content-type'].split('charset=')[-1]

        if encoding not in('text/html', 'text/plain'):
            try:
                raw_html = unicode(page.read(), encoding)
            except:
                self.warn('Can not read {0}'.format(encoding))
                return
        else:
            raw_html = page.read()

        # remove comments, they screw with BeautifulSoup
        clean_html = sub(r'<!--.*?-->', r'', raw_html.encode('utf-8'), flags=re.DOTALL)

        soup = BeautifulSoup(clean_html)

        texts = soup.findAll(text=True)
        visible_text = filter(self.visible_tags, texts)

        self.process_text(visible_text)

        self.populate(soup)

        self.analyze_title()
        self.analyze_description()
        self.analyze_keywords()
        self.analyze_a_tags(soup)
        self.analyze_img_tags(soup)
        self.analyze_h1_tags(soup)
        self.social_shares()

    def social_shares(self):
        fb_share_count = 0
        fb_comment_count = 0
        fb_like_count = 0
        fb_click_count = 0

        try:
            page = urlopen('http://api.ak.facebook.com/restserver.php?v=1.0&method=links.getStats&urls=%s&format=json'
                % self.url)
            fb_data = loads(page.read())
            fb_share_count = fb_data[0]['share_count']
            fb_comment_count = fb_data[0]['comment_count']
            fb_like_count = fb_data[0]['like_count']
            fb_click_count = fb_data[0]['click_count']
        except:
            pass

        print 'facebook\t{0}\t{1}\t{2}\t{3}\t{4}'.format(self.url, fb_share_count,
            fb_comment_count, fb_like_count, fb_click_count)

        twitter_count = 0

        try:
            page = urlopen('http://urls.api.twitter.com/1/urls/count.json?url=%s&callback=twttr.receiveCount' % self.url)
            twitter_count = loads(page.read()[19:-2])['count']
        except:
            pass

        print 'twitter\t{0}\t{1}'.format(self.url, twitter_count)

        su_views = 0

        try:
            page = urlopen('http://www.stumbleupon.com/services/1.01/badge.getinfo?url=%s' % self.url)
            su_data = loads(page.read())
            if 'result' in su_data and 'views' in su_data['result']:
                su_views = su_data['result']['views']
        except:
            pass

        print 'stumbleupon\t{0}\t{1}'.format(self.url, su_views)

    def translate_non_alphanumerics(self, to_translate, translate_to=u' '):
        not_letters_or_digits = u'!"#%\'()*+,-./:;<=>?@[\]^_`{|}~'
        translate_table = dict((ord(char), translate_to) for char in not_letters_or_digits)
        return to_translate.translate(translate_table)

    def tokenize(self, rawtext):
        return [word for word in TOKEN_REGEX.findall(rawtext.lower()) if word not in ENGLISH_STOP_WORDS]

    def process_text(self, vt):
        page_text = ''

        for element in vt:
            page_text += element.encode('utf-8').lower() + ' '

        tokens = self.tokenize(page_text.decode('utf-8'))

        freq_dist = nltk.FreqDist(tokens)

        for word in freq_dist:
            root = stemmer.stem_word(word)

            if root in stem_to_word and freq_dist[word] > stem_to_word[root]['count']:
                stem_to_word[root] = {'word': word, 'count': freq_dist[word]}
            else:
                stem_to_word[root] = {'word': word, 'count': freq_dist[word]}

            if root in wordcount:
                wordcount[root] += freq_dist[word]
            else:
                wordcount[root] = freq_dist[word]

    def analyze_title(self):
        """
        Validate the title
        """

        # getting lazy, create a local variable so save having to
        # type self.x a billion times
        t = self.title

        # calculate the length of the title once
        length = len(t)

        if length == 0:
            self.warn('Missing title tag')
        elif length < 10:
            self.warn('Title tag is too short')
        elif length > 70:
            self.warn('Title tag is too long')

    def analyze_description(self):
        """
        Validate the description
        """

        # getting lazy, create a local variable so save having to
        # type self.x a billion times
        d = self.description

        # calculate the length of the description once
        length = len(d)

        if length == 0:
            self.warn('Missing description')
        elif length < 140:
            self.warn('Description is too short')
        elif length > 255:
            self.warn('Description is too long')

    def analyze_keywords(self):
        """
        Validate keywords
        """

        # getting lazy, create a local variable so save having to
        # type self.x a billion times
        k = self.keywords

        # calculate the length of keywords once
        length = len(k)

        if length == 0:
            self.warn('Missing keywords')

    def visible_tags(self, element):
        if element.parent.name in ['style', 'script', '[document]']:
            return False
        return True

    def analyze_img_tags(self, bs):
        """
        Verifies that each img has an alt and title
        """
        images = bs.find_all('img')

        for image in images:
            if 'alt' not in image:
                self.warn('Image missing alt')

            if 'title' not in image:
                self.warn('Image missing title')

    def analyze_h1_tags(self, bs):
        """
        Make sure each page has at least one H1 tag
        """
        htags = bs.find_all('h1')

        if len(htags) == 0:
            self.warn('Each page should have at least one h1 tag')

    def analyze_a_tags(self, bs):
        """
        Add any new links (that we didn't find in the sitemap)
        """
        anchors = bs.find_all('a', href=True)

        for tag in anchors:
            if 'title' not in tag:
                self.warn('Anchor missing title tag')

            if self.site not in tag['href'] and ':' in tag['href']:
                continue

            modified_url = self.rel_to_abs_url(tag['href'])

            if modified_url in pages_crawled:
                continue

            pages_to_crawl.append(modified_url)

    def rel_to_abs_url(self, link):
        if ':' in link:
            return link

        relative_path = link
        domain = self.site

        if domain[-1] == '/':
            domain = domain[:-1]

        if relative_path[0] != '/':
            relative_path = '/{0}'.format(relative_path)

        return '{0}{1}'.format(domain, relative_path)

    def warn(self, warning):
        self.warnings.append(warning)

def getText(nodelist):
    """
    Stolen from the minidom documentation
    """
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)

def main(site, sitemap):
    if sitemap is not None:
        page = urlopen(sitemap)
        xml_raw = page.read()
        xmldoc = minidom.parseString(xml_raw)
        urls = xmldoc.getElementsByTagName('loc')

        for url in urls:
            pages_to_crawl.append(getText(url.childNodes))

    pages_to_crawl.append(site)

    for page in pages_to_crawl:
        pg = Page(page, site)
        pg.analyze()
        pg.talk('warnings')

    sorted_words = sorted(wordcount.iteritems(), key=itemgetter(1), reverse=True)

    for word in sorted_words:
        print "{0}\t{1}".format(stem_to_word[word[0]]['word'].encode('utf-8'), word[1])

if __name__ == "__main__":
    site = ''
    sitemap = ''

    if len(sys.argv) == 2:
        site = sys.argv[1]
        sitemap = None
    elif len(sys.argv) == 3:
        site = sys.argv[1]
        sitemap = site + sys.argv[2]
    else:
        print "Usage: python analyze.py http://www.site.tld [sitemap]"
        exit()

    main(site, sitemap)


