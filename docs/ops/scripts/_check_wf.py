import yaml, re, textwrap, ast, sys

d = yaml.safe_load(open('.github/workflows/v8_algo_run.yml', encoding='utf-8'))
bad = 0
for s in d['jobs']['algo']['steps']:
    if s.get('shell') != 'powershell':
        continue
    body = s.get('run', '')
    non = [(i + 1, l) for i, l in enumerate(body.splitlines())
           if any(ord(c) > 127 for c in l)]
    print('STEP:', s.get('name', '')[:34], '| non-ascii lines:', len(non))
    for n, l in non[:8]:
        print('    L%d: %s' % (n, l.strip()[:70]))
        bad += 1

run = d['jobs']['algo']['steps'][0]['run']
code = textwrap.dedent(re.search(r"\$code = @'\n(.*?)\n'@", run, re.S).group(1))
ast.parse(code)
print('PYTHON SYNTAX OK')
print('TOTAL non-ascii powershell lines:', bad)
sys.exit(1 if bad else 0)
