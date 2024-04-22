from dataClass import Client as Cl

class DataServiceRestaurant(Cl):

    def __init__(self, nickName, rating, place, street, city, country):
        super().__init__(nickName, rating, place, street, city, country)
        self.dataList = list(tuple())

    def __str__(self):
        return self.dataList
    
    def addData(self, nickName, rating, place, street, city, country):
        self.dataList.append(Cl(nickName, rating, place, street, city, country))

    def removeData(self, nickName, rating, place, street, city, country):
        for client in self.dataList:
            if client.nickName == nickName and client.rating == rating and client.place == place and client.street == street and client.city == city and client.country == country:
                self.dataList.remove(client)
                return
            
    def sortData(self, dataList):
        dataList.sort(key = lambda x: (x.place, x.street, x.city, x.country))

    def showData(self, dataList):
        for i in dataList:
            print(i)
    
    def insertData(self, nickName, rating, place, street, city, country):
        new_client = Cl(nickName, rating, place, street, city, country)
        self.dataList.append(new_client)
        i = len(self.dataList) - 1
        while i > 0 and self.dataList[i - 1].nickName > new_client.nickName:
            self.dataList[i] = self.dataList[i - 1]
            i -= 1
        self.dataList[i] = new_client
<<<<<<< Updated upstream

    def searchData(self, place, street, city, country):
        left, right = 0, len(self.dataList) - 1

        while left <= right:
            mid = (left + right) // 2
            if (self.dataList[mid].place, self.dataList[mid].street, self.dataList[mid].city, self.dataList[mid].country) < (place, street, city, country):
                left = mid + 1
            elif (self.dataList[mid].place, self.dataList[mid].street, self.dataList[mid].city, self.dataList[mid].country) > (place, street, city, country):
                right = mid - 1
            else:
                return mid  # Znaleziono element

        return -1

    def searchAllData(self, place, street, city, country):
        # Filter the dataList to include only elements that match at least one criterion.
        matches = list(filter(lambda x: x.place == place or x.street == street or x.city == city or x.country == country, self.dataList))

        # If no matches were found, return -1.
        if not matches:
            return -1

        # Define a function that counts the number of matches for a given element.
        def count_matches(x):
            return sum([x.place == place, x.street == street, x.city == city, x.country == country])

        # Sort the matches from most to least.
        matches.sort(key=count_matches, reverse=True)

        return matches
=======
>>>>>>> Stashed changes
