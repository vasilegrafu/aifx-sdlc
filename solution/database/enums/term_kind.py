from enum import Enum

"""------------------------------------------------------------------------------------------------
"""
class TermKind(Enum):
    FALL = ('F', 'Fall')
    SPRING = ('SP', 'Spring')
    SUMMER = ('SU', 'Summer')
    WINTER = ('W', 'Winter')

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
        raise ValueError(f'Unknown term kind code: {code}')

"""------------------------------------------------------------------------------------------------
"""
if __name__ == '__main__':
    print(TermKind.FALL)
    print(TermKind.FALL.code)
    print(TermKind.FALL.label)
    print()
    print(TermKind.from_code('F'))
