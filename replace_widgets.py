"""
Bulk widget replacement script
Replaces standard Qt widgets with custom glassmorphic widgets
"""

import re
from pathlib import Path

# Files to process
files_to_process = [
    "app/widgets/encoder_tab.py",
    "app/widgets/subtitle_tab.py",
    "app/widgets/metadata_tab.py",
]

# Replacement patterns
replacements = {
    r'\bQLabel\(': 'StyledLabel(',
    r'\bQCheckBox\(': 'StyledCheckBox(',
    r'\bQComboBox\(': 'StyledComboBox(',
    r'\bQLineEdit\(': 'StyledLineEdit(',
    r'\bQSpinBox\(': 'StyledSpinBox(',
    r'\bQTextEdit\(': 'StyledTextEdit(',
}

# Import additions needed
import_additions = {
    "app/widgets/encoder_tab.py": [
        "StyledCheckBox",
        "StyledComboBox",
        "StyledLabel",
        "StyledLineEdit",
        "StyledSpinBox",
    ],
    "app/widgets/subtitle_tab.py": [
        "GlassmorphicButton",
        "GlassmorphicCard",
        "StyledCheckBox",
        "StyledComboBox",
        "StyledLabel",
        "StyledLineEdit",
        "StyledSpinBox",
        "StyledTextEdit",
    ],
    "app/widgets/metadata_tab.py": [
        "GlassmorphicButton",
        "GlassmorphicCard",
        "StyledCheckBox",
        "StyledComboBox",
        "StyledLabel",
        "StyledLineEdit",
        "StyledSpinBox",
        "StyledTextEdit",
    ],
}

def process_file(filepath):
    """Process a single file"""
    path = Path(filepath)
    if not path.exists():
        print(f"❌ File not found: {filepath}")
        return
    
    print(f"\n📝 Processing: {filepath}")
    
    # Read file
    content = path.read_text(encoding='utf-8')
    original_content = content
    
    # Apply replacements
    changes_made = 0
    for pattern, replacement in replacements.items():
        matches = len(re.findall(pattern, content))
        if matches > 0:
            content = re.sub(pattern, replacement, content)
            changes_made += matches
            print(f"  ✓ Replaced {matches} instances: {pattern} -> {replacement}")
    
    if changes_made > 0:
        # Write back
        path.write_text(content, encoding='utf-8')
        print(f"  ✅ Saved {changes_made} changes to {filepath}")
    else:
        print(f"  ℹ️ No changes needed")

def main():
    """Main execution"""
    print("=" * 70)
    print("ENCODEFORGE WIDGET REPLACEMENT SCRIPT")
    print("=" * 70)
    
    for filepath in files_to_process:
        process_file(filepath)
    
    print("\n" + "=" * 70)
    print("✅ REPLACEMENT COMPLETE")
    print("=" * 70)
    print("\n⚠️  NEXT STEPS:")
    print("1. Update imports in each file manually")
    print("2. Test the application: py main.py")
    print("3. Fix any remaining styling issues")

if __name__ == "__main__":
    main()
