import csv

with open("custom.csv", "r+") as f:
    f.truncate(0)
    writer = csv.writer(f)
    writer.writerow('')

while True:
    out = input()

    out = out.split(",")

    out.insert(0, "")

    for i in range(0, 5):
        out.insert(5, "")

    with open('custom.csv', 'a', newline='') as file:
        writer = csv.writer(file)

        writer.writerow(out)

    with open("custom.csv", 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')

            for song in csv_reader:
                print(song)

#Yoursforever, ultravilot, usedcvnt, , Breakcore