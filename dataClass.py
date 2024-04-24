<<<<<<< Updated upstream
import sys
=======
>>>>>>> Stashed changes

class Client():
    def __init__(self, rating, place, street, city, country, desc):
        self.desc = desc
        self.rating = rating
        self.place = place
        self.street = street
        self.city = city
        self.country = country
        

    def __str__(self):
        return f"Rating: {self.rating}, Place: {self.place}, Street: {self.street}, City: {self.city}, Country: {self.country}, Description: {self.desc}"
    
    def changeData(self):
        
        while True:
            print("What would you like to change in your opinion?")
            print("1.Rating")
            print("2.Place")
            print("3.Street")
            print("4.City")
            print("5.Country")
            print("6.Description")
            print("7.Exit")
            change = int(input())
            match change:
                case 1:
                    print("Enter new rating")
                    self.rating = int(input())
                case 2:
                    print("Enter new place")
                    self.place = input()
                case 3:
                    print("Enter new street")
                    self.street = input()
                case 4:
                    print("Enter new city")
                    self.city = input()
                case 5:
                    print("Enter new country")
                    self.country = input()
                case 6:
                    print("Enter new description")
                    self.desc = input()
                case 7:
                    sys.exit()
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
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
