#!/usr/bin/env python2

from __future__ import print_function

import os
import sys
import time
import yaml
import json
import requests

def fatal(message):
    print(message, file=sys.stderr)
    sys.exit(1)

CONFIG_FILE = os.environ['KIBANA_MANAGER_CONFIG_FILE'] if 'KIBANA_MANAGER_CONFIG_FILE' in os.environ else '/etc/kibana-manager/config.yaml'

with open(CONFIG_FILE, 'rb') as f:
    config = yaml.load(f)

if 'openshift' not in config:
    fatal('Config file missing required section "openshift"')
if 'elasticsearch' not in config:
    fatal('Config file missing required section "elasticsearch"')

if 'access_token' not in config['openshift']:
    fatal('Config file missing required section "openshift.access_token"')
if 'api_base_url' not in config['openshift']:
    fatal('Config file missing required section "openshift.api_base_url"')

if 'base_url' not in config['elasticsearch']:
    fatal('Config file missing required section "elasticsearch.base_url"')
if 'client_cert_path' not in config['elasticsearch']:
    fatal('Config file missing required section "elasticsearch.client_cert_path"')
if 'client_key_path' not in config['elasticsearch']:
    fatal('Config file missing required section "elasticsearch.client_key_path"')

if 'check_interval' not in config:
    config['check_interval'] = 30

if 'protected_patterns' not in config:
    config['protected_patterns'] = []

PROTECTED_PATTERNS = set(config['protected_patterns'])
ELASTICSEARCH_URL_PATTERN = "{0}/.kibana/index-pattern/{{0}}.*".format(config['elasticsearch']['base_url'])
ELASTICSEARCH_QUERY_URL = "{0}/.kibana/index-pattern/_search?q=_type:\"index-pattern\"".format(config['elasticsearch']['base_url'])
ELASTICSEARCH_CLIENT_CERT_PATH = config['elasticsearch']['client_cert_path']
ELASTICSEARCH_CLIENT_KEY_PATH = config['elasticsearch']['client_key_path']
NAMESPACES_URL = "{0}/api/v1/namespaces".format(config['openshift']['api_base_url'])
OPENSHIFT_HEADERS = {
	'Authorization': 'Bearer '+config['openshift']['access_token'],
	'Accept': 'application/json',
    }

def get_namespaces(s):
    r = s.get(NAMESPACES_URL, headers=OPENSHIFT_HEADERS)
    if r.status_code == 200:
        obj = r.json()
        return set([x['metadata']['name'] for x in obj['items']])
    raise Exception("Failed to get namespaces: [{0}] {1}".format(r.status_code, NAMESPACES_URL))

def main():
    s = requests.Session()
    if 'ca_cert_path' in config:
        s.verify = config['ca_cert_path']
    while True:
        namespaces = get_namespaces(s)
        r = s.get(ELASTICSEARCH_QUERY_URL, cert=(ELASTICSEARCH_CLIENT_CERT_PATH, ELASTICSEARCH_CLIENT_KEY_PATH))
        if r.status_code != 200:
            fatal("Failed to get index patterns: [{0}] {1}".format(r.status_code, ELASTICSEARCH_QUERY_URL))
        es_query_result = r.json()
        # Yes, it's ['hits']['hits'].  Really.
        index_patterns = set([x['_source']['title'] for x in es_query_result['hits']['hits']])
        for ns in namespaces:
            if ns+'.*' not in index_patterns:
                url = ELASTICSEARCH_URL_PATTERN.format(ns)
                cert_and_key = (ELASTICSEARCH_CLIENT_CERT_PATH, ELASTICSEARCH_CLIENT_KEY_PATH)
                content = {'title' : ns+'.*',
                           'timeFieldName': 'time'}
                r = s.put(url, cert=cert_and_key, data=json.dumps(content))
                if r.status_code != 200 and r.status_code != 201:
                    print("Failed to create Kibana index pattern for OpenShift namespace {0} (response code {1})".format(ns, r.status_code), file=sys.stderr)
                else:
                    print("Created Kibana index pattern for OpenShift namespace {0})".format(ns))
        for pattern in index_patterns:
            ns = pattern.split('.')[0]
            if pattern not in PROTECTED_PATTERNS and ns not in namespaces:
                url = ELASTICSEARCH_URL_PATTERN.format(ns)
                cert_and_key = (ELASTICSEARCH_CLIENT_CERT_PATH, ELASTICSEARCH_CLIENT_KEY_PATH)
                r = s.delete(url, cert=cert_and_key)
                if r.status_code != 200:
                    print("Failed to delete Kibana index pattern for dead OpenShift namespace {0} (response code {1})".format(ns, r.status_code), file=sys.stderr)
                else:
                    print("Deleted Kibana index pattern for dead OpenShift namespace {0}".format(ns))
        time.sleep(config['check_interval'])

if __name__ == '__main__':
    main()