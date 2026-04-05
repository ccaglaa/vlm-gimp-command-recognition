gimp -nidfs --quit --batch-interpreter=python-fu-eval -b @"
exec(open('batch.py').read())
"@