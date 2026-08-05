from enum import Enum

"""------------------------------------------------------------------------------------------------
"""
class EnrollmentStatus(Enum):
    ENROLLED = ('EN', 'Enrolled')
    COMPLETED = ('CO', 'Completed')
    FAILED = ('FA', 'Failed')
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
        raise ValueError(f'Unknown enrollment status code: {code}')

"""------------------------------------------------------------------------------------------------
"""
if __name__ == '__main__':
    print(EnrollmentStatus.ENROLLED)
    print(EnrollmentStatus.ENROLLED.code)
    print(EnrollmentStatus.ENROLLED.label)
    print()
    print(EnrollmentStatus.from_code('EN'))
