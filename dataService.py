from dataClass import Client as Cl

class DataServiceRestaurant(Cl):

    def __init__(self,rating, place, street, city, country, desc):
        super().__init__(rating, place, street, city, country, desc)
        self.dataList = list(tuple())

    def __str__(self):
        return self.dataList
    
    def addData(self,rating, place, street, city, country, desc):
        self.dataList.append(Cl(rating, place, street, city, country, desc))

    def removeData(self, rating, place, street, city, country, desc):
        for client in self.dataList:
            if client.rating == rating and client.place == place and client.street == street and client.city == city and client.country == country and client.desc == desc:
                self.dataList.remove(client)
                return


    def sortData(self, dataList):
        dataList.sort(key = lambda x: (x.place, x.street, x.city, x.country))

    def sortByRating(self, dataList):
        dataList.sort(key = lambda x: x.rating)

    def sortByPlace(self, dataList):
        dataList.sort(key = lambda x: x.place)

    def sortByStreet(self, dataList):
        dataList.sort(key = lambda x: x.street)

    def sortByCity(self, dataList):
        dataList.sort(key = lambda x: x.city)
    
    def sortByCountry(self, dataList):
        dataList.sort(key = lambda x: x.country)

    def showData(self, dataList):
        for i in dataList:
            print(i)
    
    def insertData(self, rating, place, street, city, country, desc):
        new_client = Cl(rating, place, street, city, country, desc)
        self.dataList.append(new_client)
        i = len(self.dataList) - 1
        while i > 0 and self.dataList[i - 1].place > new_client.place:
            self.dataList[i] = self.dataList[i - 1]
            i -= 1
        self.dataList[i] = new_client

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
