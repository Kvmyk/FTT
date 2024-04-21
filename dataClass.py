class Client():
    def __init__(self, nickName, rating, place, street, city, country):
        self.nickName = nickName
        self.rating = rating
        self.place = place
        self.street = street
        self.city = city
        self.country = country
        

    def __str__(self):
        return f"NickName: {self.nickName}, Rating: {self.rating}, Place: {self.place}, Street: {self.street}, City: {self.city}, Country: {self.country}"
    
    def changeData(self):
        
        while True:
            print("What would you like to change in your opinion?")
            print("1. Nickname")
            print("2. Rating")
            print("3. Place")
            print("4. Street")
            print("5. City")
            print("6. Country")
            print("7. Exit")
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
                    self.country = input("Enter new country: ")
                case 7:
                    break
                case _:
                    print("Invalid option")
            print("Your opinion has been changed")
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