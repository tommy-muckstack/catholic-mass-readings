#!/usr/bin/env python3
"""
Test section type parsing
"""

# Mock the SectionType enum
class SectionType:
    UNKNOWN = "UNKNOWN"
    READING = "READING"
    GOSPEL = "GOSPEL"
    PSALM = "PSALM"
    ALLELUIA = "ALLELUIA"
    SEQUENCE = "SEQUENCE"
    ALTERNATIVE = "ALTERNATIVE"
    
    @classmethod
    def from_header(cls, header: str):
        header = header.casefold()
        if "alleluia" in header:
            return cls.ALLELUIA
        if "gospel" in header:
            return cls.GOSPEL
        if "psalm" in header:
            return cls.PSALM
        if "sequence" in header:
            return cls.SEQUENCE
        if "reading" in header:
            return cls.READING
        if "or" in header:
            return cls.ALTERNATIVE
        return cls.UNKNOWN

def test_headers():
    """Test the headers we found in the USCCB page"""
    
    headers = [
        "Reading 1",
        "Responsorial Psalm", 
        "Alleluia",
        "Gospel"
    ]
    
    print("🧪 Testing Section Type Recognition:")
    for header in headers:
        section_type = SectionType.from_header(header)
        print(f"  '{header}' → {section_type}")
        
    print(f"\n✅ All headers should map to known section types (not UNKNOWN)")

if __name__ == "__main__":
    test_headers()