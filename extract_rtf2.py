"""
RTF extractor for CaseCATalyst deposition files.
Preserves Q/A/colloquy structure using style codes.
"""
import re

with open('031326yellowrock-ROUGH_T_1.rtf', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# The RTF styles:
# s1 = Question 1, s2 = Que Contin 1
# s3 = Answer 1, s4 = Ans Contin 1
# s5 = Colloquy 1, s6 = Col Contin 1
# s7 = By Line 1

# Split into paragraphs by \par
# Each paragraph starts with \pard or style info

def clean_rtf_text(text):
    """Remove RTF codes from a text segment, return plain text."""
    # Remove steno blocks {\*\cx...} and {\*\cxt...}
    text = re.sub(r'\{\\\*\\cx[^}]{0,500}\}', '', text)
    # Remove remaining steno
    text = re.sub(r'\\cx[a-z]+[0-9]*\*?\s?', '', text)
    # Handle special chars
    text = text.replace('\\line', '\n')
    text = text.replace('\\page', '\n')
    text = text.replace('\\tab', '    ')
    text = text.replace('\\~', '\u00a0')  # non-breaking space
    # Remove RTF control words
    text = re.sub(r'\\[a-zA-Z]+[-]?[0-9]*\*?\s?', '', text)
    # Remove braces
    text = re.sub(r'\{[^{}]*\}', '', text)
    text = re.sub(r'[{}\\]', '', text)
    # Clean whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()
    return text

# Parse paragraph blocks
# Each \pard...\s<N> starts a new paragraph with style N
# We'll split on \par\pard patterns

# First, let's do a paragraph-level parse
# Split content by paragraph markers
paragraphs = re.split(r'\\par(?:d)?', content)

output_lines = []
page_num = 1
line_num = 1

for para in paragraphs:
    # Detect page break
    if '\\page' in para and '\\paperh' not in para:
        page_num += 1
        line_num = 1
        output_lines.append(f'\n--- PAGE {page_num} ---\n')
        continue

    # Detect style
    style_match = re.search(r'\\s(\d+)', para)
    style = int(style_match.group(1)) if style_match else 0

    # Clean the text
    text = clean_rtf_text(para)

    if not text or len(text) < 2:
        continue

    # Assign labels based on style
    if style == 1 or style == 2:  # Question
        label = 'Q.  '
    elif style == 3 or style == 4:  # Answer
        label = 'A.  '
    elif style == 5 or style == 6:  # Colloquy
        label = ''
    elif style == 7 or style == 8:  # By Line
        label = ''
    else:
        label = ''

    output_lines.append(f'{label}{text}')
    line_num += 1

result = '\n'.join(output_lines)
# Clean up multiple blank lines
result = re.sub(r'\n{3,}', '\n\n', result)

with open('extracted_qa.txt', 'w', encoding='utf-8') as f:
    f.write(result)

print(f'Done. Length: {len(result)}')
print('First 3000 chars:')
print(result[:3000])
