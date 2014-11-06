import json
from csv import DictReader
from StringIO import StringIO
from operator import itemgetter
from os.path import join, dirname, splitext
from dateutil.parser import parse as parse_datetime
from os import environ

from jinja2 import Environment, FileSystemLoader
from requests import get

from . import S3, paths

def load_states(s3):
    # Find existing cache information
    state_key = s3.get_key('state.txt')
    states = list()

    if state_key:
        state_link = state_key.get_contents_as_string()
        if '\t' not in state_link:
            # it's probably a link to someplace else.
            state_key = s3.get_key(state_link.strip())
    
    if state_key:
        last_modified = parse_datetime(state_key.last_modified)
        state_file = StringIO(state_key.get_contents_as_string())
        
        for row in DictReader(state_file, dialect='excel-tab'):
            row['shortname'], _ = splitext(row['source'])
            row['href'] = row['processed'] or row['cache'] or None
            row['href'] = 'https://github.com/openaddresses/openaddresses/blob/master/sources/' + row['source']
            
            if row.get('version', False):
                v = row['version']
                row['cache_date'] = '{}-{}-{}'.format(v[0:4], v[4:6], v[6:8])
            else:
                row['cache_date'] = None

            row['class'] = ' '.join([
                'cached' if row['cache'] else '',
                'processed' if row['processed'] else '',
                ])
            
            with open(join(paths.sources, row['source'])) as file:
                data = json.load(file)
            
                row['type'] = data.get('type', '').lower()
                row['conform'] = bool(data.get('conform', False))
            
            if row.get('sample', False):
                row['sample_data'] = get(row['sample']).json()
            
            if not row.get('sample_data', False):
                row['sample_data'] = list()
            
            states.append(row)
    
    states.sort(key=lambda s: (bool(s['cache']), bool(s['processed']), s['source']))
    
    return last_modified, states

def main():
    s3 = S3(environ['AWS_ACCESS_KEY_ID'], environ['AWS_SECRET_ACCESS_KEY'], 'openaddresses-cfa')
    print summarize(s3).encode('utf8')

def summarize(s3):
    ''' Return summary HTML.
    '''
    env = Environment(loader=FileSystemLoader(join(dirname(__file__), 'templates')))
    env.filters['tojson'] = lambda value: json.dumps(value, ensure_ascii=False)
    template = env.get_template('state.html')
    last_modified, states = load_states(s3)
    return template.render(states=states, last_modified=last_modified)

if __name__ == '__main__':
    exit(main())