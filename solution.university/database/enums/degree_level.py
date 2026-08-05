from enum import Enum

"""------------------------------------------------------------------------------------------------
"""
class DegreeLevel(Enum):
    BACHELOR = ('BA', 'Bachelor')
    MASTER = ('MA', 'Master')
    DOCTORATE = ('PHD', 'Doctorate')

    @property
    def code(self):
        return self.value[0]

    @property
    def label(self):
        return self.value[1]

    @classmethod
    def from_code(cls, code):
        for entry in cls:
            if entry.code == code:
                return entry
        raise ValueError(f'Unknown degree level code: {code}')

"""------------------------------------------------------------------------------------------------
"""
if __name__ == '__main__':
    print(DegreeLevel.BACHELOR)
    print(DegreeLevel.BACHELOR.code)
    print(DegreeLevel.BACHELOR.label)
    print()
    print(DegreeLevel.from_code('BA'))
