import os
import glob
for root, _, files in os.walk('backend'):
    for f in files:
        if f.endswith('.py'):
            with open(os.path.join(root, f), 'r', encoding='utf-8') as file:
                lines = file.readlines()
                for i, l in enumerate(lines):
                    if 'save_trade_signal' in l:
                        print(f'{root}/{f}:{i} {l.strip()}')
