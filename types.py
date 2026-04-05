import random

class paramNumber() : 
    def __init__(
            self, 
            minVal,
            maxVal):
        self.minVal = minVal
        self.maxVal = maxVal 

class paramInteger(paramNumber) : 
    
    def __init__(self, minVal, maxVal):
        super().__init__(minVal, maxVal)

    def getRandomValue(self):
        return random.randint(self.minVal, self.maxVal)

class paramDouble(paramNumber) :
    
    def __init__(self, minVal, maxVal):
        super().__init__(minVal, maxVal)

    def getRandomValue(self) :
        return (random.random() * (self.maxVal - self.minVal)) - ((self.maxVal - self.minVal) / 2)

class paramString () :

    def __init__(self,domain):
        self.domain = list()
        for e in domain : 
            self.domain.append(e)
    
    def getRandomValue(self) :
        return self.domain[random.randint(0, len(self.domain) - 1)]