ProgramEnrollment Model Data Integrity
--------------------------------------

Status
======

Accepted (circa August 2019)


Context
=======

For the sake of fundamental data integrity, we are introducing 2 unique
constraints on the ``program_enrollments.ProgramEnrollment`` model.

Decisions
=========

The unique constraints are on the following column sets:

* ``('user', 'program_uuid')``

Consequences
============

The first constraint supports the cases in which we save program enrollment records
that don't have any association with an external organization, e.g. our MicroMasters programs.
Non-realized enrollments, where the ``user`` value is null, are not affected by this constraint.
