from .interface import RoleUsersImp


class ProgramStaffRoles(RoleUsersImp):
    """A Staff member of a program team"""
    ROLE = 'staff'

    def __init__(self, program_uuid):
        super(ProgramStaffRoles, self).__init__(self.ROLE, program_uuid)


class ProgramInstructorRole(RoleUsersImp):
    """A Instructor member(Admin) of a program team"""
    ROLE = 'instructor'

    def __init__(self, program_uuid):
        super(ProgramInstructorRole, self).__init__(self.ROLE, program_uuid)
