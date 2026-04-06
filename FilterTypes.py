import random
import json 

"""
This scipt allows you to read a json file which contains a procedure and 
retrive its name alongside its arguments name, types and field. 
"""

# If a value is +inf or -inf, it will be rounded down/up to this value
# This is for practical reasons, having an infinite value for random is bad 
BOUND_INF = 10000

class ParamNumber() : 
    def __init__(
            self, 
            name,
            minVal,
            maxVal
            ):
        self.name = name 
        self.minVal = minVal
        self.maxVal = maxVal 
    
    def toString (self) -> str : 
        return "Parameter name : " + self.name 

class ParamInteger(ParamNumber) : 
    
    def __init__(self, name : str, minVal : int, maxVal : int):
        super().__init__(name, minVal, maxVal)

    def getRandomValue(self) -> int :
        return random.randint(self.minVal, self.maxVal)
    
    def toString(self):
        return super().toString() + f", Type : Int, minVal : {self.minVal}, maxVal : {self.maxVal}"
    

class ParamDouble(ParamNumber) :
    
    def __init__(self, name : str, minVal : float, maxVal : float):
        super().__init__(name, minVal, maxVal)

    def getRandomValue(self) -> float :
        return (random.random() * (self.maxVal - self.minVal)) - ((self.maxVal - self.minVal) / 2)
    
    def toString(self):
        return super().toString() + f", Type : Float, minVal : {self.minVal:.2f}, maxVal : {self.maxVal:.2f}"

class ParamBoolean : 
    def __init__(
            self,
            name : str
            ):
        self.name = name 
    
    def getRandomValue(self) -> bool : 
        return random.random() < 0.5

    def toString(self) :
        return "Name : " + self.name + ", Type : Boolean"

class ParamString () :

    def __init__(self,name : str,domain : list[str]):
        self.name = name 
        self.domain = list()
        for e in domain : 
            self.domain.append(e)
    
    def getRandomValue(self) -> str :
        return self.domain[random.randint(0, len(self.domain) - 1)]
    
    def toString(self) : 
        s = f"Parameter name : {self.name}, Type : String, Domain :"
        for i in range(len(self.domain) - 1) : 
            s += self.domain[i] + ", "
        return s + self.domain[-1]
    

class Filter :
    """
    Classe représentant un filtre, avec son nom entier ainsi que 
    ses paramètres 
    """
    def __init__(self, name : str):
        """
        Initialise un filtre avec son nom, et avec une liste de paramètres vide 
        """
        self.name = name 
        self.parameters : list[ParamBoolean | ParamDouble | ParamInteger |ParamString] = list()

    def addParameter (
            self,
            param : ParamBoolean | ParamDouble | ParamInteger |ParamString
            ) : 
        """
        Cette fonction ajoute un paramètre au filtre.\n
        Ne vérifie pas si celui-ci est déjà présent 
        """
        self.parameters.append(param)

    def toString(self) : 
        s = "Plugin name : " + self.name + "\n"
        for e in self.parameters : 
            s += "--" + e.toString() + "\n"
        return s 

def convertStringToValue (s : str | int) -> int : 
    if (s != None and type(s) == str) : 
        if (s == "+inf") : 
            return BOUND_INF
        return -BOUND_INF
    else : 
        return s 

def convertDictToParameter (parameter : dict) : 
    match parameter["type"] :

        case "gint" : 
            minVal, maxVal = convertStringToValue(parameter["field"]["minVal"]), convertStringToValue(parameter["field"]["maxVal"])
            return ParamInteger(parameter["name"], minVal, maxVal)
             
        case "guint" : 
            minVal, maxVal = convertStringToValue(parameter["field"]["minVal"]), convertStringToValue(parameter["field"]["maxVal"])
            return ParamInteger(parameter["name"], minVal, maxVal)
        
        case "gchararray" : 
            domain = parameter["field"]
            return ParamString(parameter["name"], domain)

        case "gdouble" : 
            minVal, maxVal = convertStringToValue(parameter["field"]["minVal"]), convertStringToValue(parameter["field"]["maxVal"])
            return ParamDouble(parameter["name"], minVal, maxVal)
        
        case "gboolean" : 
            return ParamBoolean(parameter["name"])

        case _ :
            raise TypeError ("The type " + parameter["paramType"] + " is not handled yet.")


def convertDictToFilter (filter : dict) :
    res = Filter(filter["procedureName"])

    s : str = "param"
    i : int = 1

    while (s + str(i) in filter.keys()) :
        res.addParameter(convertDictToParameter(filter[s + str(i)]))
        i += 1 
    
    return res 

filePath = r"C:\Users\Andy\Documents\DossierLicence\Dossier_Master\pai2d-2026\listeProcedures.json"

data = None

with open(filePath) as f : 
    data = json.load(f)

print(convertDictToFilter(data[0]).toString())

