from dataClass import Client as Cl

class DataService(Cl):

    def __init__(self, name, surName, age, amount, data):
        super().__init__(name, surName, age, amount, data)
        self.dataList = list(tuple())

    def __str__(self):
        return self.dataList
    
    def addData(self, name, surName, age, amount, data):
        self.dataList.append(Cl(name, surName, age, amount, data))

    def removeData(self, name, surName, age, amount, data):
        for client in self.dataList:
            if (client.name == name and client.surName == surName and client.age == age and 
                client.amount == amount and client.data == data):
                self.dataList.remove(client)
                break
    def sortData(self, dataList):
        dataList.sort(key = lambda x: x.name)

    def showData(self, dataList):
        for i in dataList:
            print(i)
    
    def insertData(self, name, surName, age, amount, data):
        new_client = Cl(name, surName, age, amount, data)
        self.dataList.append(new_client)
        i = len(self.dataList) - 1
        while i > 0 and self.dataList[i - 1].name > new_client.name:
            self.dataList[i] = self.dataList[i - 1]
            i -= 1
        self.dataList[i] = new_client