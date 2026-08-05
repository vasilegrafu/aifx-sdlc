from enum import Enum

"""------------------------------------------------------------------------------------------------
"""
class StudentStatus(Enum):
    APPLIED = ('AP', 'Applied')
    ACTIVE = ('AC', 'Active')
    ON_LEAVE = ('OL', 'On Leave')
    SUSPENDED = ('SU', 'Suspended')
    GRADUATED = ('GR', 'Graduated')
    WITHDRAWN = ('WD', 'Withdrawn')

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
        raise ValueError(f'Unknown student status code: {code}')

"""------------------------------------------------------------------------------------------------
"""
if __name__ == '__main__':
    print(StudentStatus.ACTIVE)
    print(StudentStatus.ACTIVE.code)
    print(StudentStatus.ACTIVE.label)
    print()
    print(StudentStatus.from_code('AC'))
