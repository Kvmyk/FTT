class Menu():
    def __init__(self, options):
        self.options = options

    def optionService(self):
        match self.options:
            case "1":
                print("Restaurant")
            case "2":
                print("Hotel")
            case "3":
                print("Attraction")
            case "4":
                print("Exit")
            case _:
                print("Invalid choice")

    def showMenu(self):
        print("Select one of the following options: ")
        print("1. Restaurant")
        print("2. Hotel")
        print("3. Attraction")
        print("4. Exit")
        self.options = input("Enter your choice: ")
        self.optionService()
    