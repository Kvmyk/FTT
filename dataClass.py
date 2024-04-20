class Client():
    def __init__(self, name, surName, age, amount, data):
        self.name = name
        self.surName = surName
        self.age = age
        self.amount = amount
        self.data = data

    def __str__(self):
        return f"{self.name} {self.surName} {self.age} {self.amount} {self.data}"
    
    def changeData(self):
        while True:
            print("What would you like to change in your reservation?")
            print("1. Name")
            print("2. Surname")
            print("3. Age")
            print("4. Amount")
            print("5. Data")
            print("6. Exit")
            change = int(input())
            match change:
                case 1:
                    self.name = input("Enter new name: ")
                case 2:
                    self.surName = input("Enter new surname: ")
                case 3:
                    self.age = input("Enter new age: ")
                case 4:
                    self.amount = input("Enter new amount: ")
                case 5:
                    self.data = input("Enter new data: ")
                case 6:
                    print("Exit")
                case _:
                    print("Invalid option")
            print("Your reservation has been changed")
            while True: 
                print("Would you like to change anything else? Y/N")
                answer = input()
                match answer:
                    case "Y":
                        continue
                    case "N":
                        break
                    case _:
                        print("Invalid option")