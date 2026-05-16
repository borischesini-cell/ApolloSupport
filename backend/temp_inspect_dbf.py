from dbfread import DBF
import os

dbf_path = r"p:\ApolloSupport\bases\CLIGESCO.DBF"
if not os.path.exists(dbf_path):
    print("DBF file not found at:", dbf_path)
else:
    table = DBF(dbf_path, encoding='latin1')
    with open("dbf_fields.txt", "w", encoding="utf-8") as f:
        f.write("Fields in CLIGESCO.DBF:\n")
        for field in table.fields:
            f.write(f"Name: {field.name:<15} Type: {field.type:<5} Length: {field.length:<5}\n")
    print("Field list saved to dbf_fields.txt")
