import json
import os
import random
import string

def generate_unique_rid(index):
    """Generate unique 8-digit rid"""
    # Start from a base number and increment
    base = 65478902
    return str(base + index)

def generate_unique_docid(index):
    """Generate unique docid following pattern: number-number-text-number-letter-number"""
    # Generate components with variation
    part1 = 98979 + index
    part2 = 99999 + (index * 7) % 10000  # Some variation
    part3 = random.choice(['xyz', 'abc', 'def', 'ghi', 'jkl', 'mno', 'pqr', 'stu', 'vwx'])
    part4 = index % 10
    part5 = chr(97 + (index % 26))  # letter a-z
    part6 = (index % 9) + 1

    return f"{part1}-{part2}-{part3}-{part4}-{part5}-{part6}"

def update_docs_in_folder(folder_path):
    """Update all JSON files in the specified folder"""
    # Get all JSON files
    json_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.json')])

    print(f"Found {len(json_files)} JSON files to update")

    updated_count = 0

    for index, filename in enumerate(json_files):
        file_path = os.path.join(folder_path, filename)

        try:
            # Read the JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Generate unique rid and docid
            new_rid = generate_unique_rid(index)
            new_docid = generate_unique_docid(index)

            # Update the fields
            data['rid'] = new_rid
            data['docid'] = new_docid

            # Write back to file with proper formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"Updated {filename}: rid={new_rid}, docid={new_docid}")
            updated_count += 1

        except Exception as e:
            print(f"Error updating {filename}: {str(e)}")

    print(f"\nSuccessfully updated {updated_count} files")

if __name__ == "__main__":
    # Set random seed for reproducibility
    random.seed(42)

    docs_folder = "docs2"
    update_docs_in_folder(docs_folder)
