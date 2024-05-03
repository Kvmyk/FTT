

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
    