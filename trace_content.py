files = ['raw_text.txt', 'cleaned_text.txt', 'corrected_text.txt']
for f in files:
    try:
        text = open(f, encoding='utf-8').read()
        found = 'ready to go' in text.lower() or 'state your' in text.lower()
        print(f'{f}: {"FOUND" if found else "MISSING"} ({len(text)} chars)')
    except:
        print(f'{f}: NOT FOUND ON DISK')
