import re
import glob
import sys

rtf_files = glob.glob('*.rtf')
if not rtf_files:
    print('ERROR: No .rtf file found in current directory.')
    sys.exit(1)
if len(rtf_files) > 1:
    print(f'WARNING: Multiple .rtf files found: {rtf_files}. Using: {rtf_files[0]}')
rtf_file = rtf_files[0]
print(f'Reading: {rtf_file}')

with open(rtf_file, 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Remove steno-specific blocks with nested braces approach
# Remove {\*\cx...} blocks
content = re.sub(r'\{\\\*\\cx[^}]{0,200}\}', '', content)
content = re.sub(r'\\cxsgdelsteno[01]', '', content)
content = re.sub(r'\\cxfl\s*', '', content)
content = re.sub(r'\\cxsingle\s*', '', content)
content = re.sub(r'\\cxdouble\s*', '', content)
content = re.sub(r'\\cxsgnocap\s*', '', content)
content = re.sub(r'\\cxsgindex[0-9]+\s*', '', content)
content = re.sub(r'\\cxsgmargin[0-9]+\s*', '', content)
content = re.sub(r'\\cxsg[a-z]+[0-9]*\s*', '', content)
content = re.sub(r'\\cx[a-z]+[0-9]*\s*', '', content)

# Convert RTF structural elements
content = content.replace('\\line ', '\n')
content = content.replace('\\line\n', '\n')
content = content.replace('\\line', '\n')
content = content.replace('\\page ', '\n--- PAGE BREAK ---\n')
content = content.replace('\\page\n', '\n--- PAGE BREAK ---\n')
content = content.replace('\\page', '\n--- PAGE BREAK ---\n')

# Replace par/pard with newlines
content = re.sub(r'\\pard[^\\{}\n]*', '\n', content)
content = re.sub(r'\\par\s', '\n', content)
content = content.replace('\\par', '\n')
content = content.replace('\\tab', '    ')

# Remove RTF control words
content = re.sub(r'\\[a-zA-Z]+[-]?[0-9]*\*?\s?', '', content)

# Remove remaining braces
content = re.sub(r'\{[^{}]*\}', '', content)
content = re.sub(r'[{}\\]', '', content)

# Clean up whitespace
content = re.sub(r'[ \t]+', ' ', content)
content = re.sub(r'\n{3,}', '\n\n', content)
content = content.strip()

with open('extracted_text.txt', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done, length:', len(content))
print(repr(content[:500]))
