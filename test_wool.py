import pexpect
import sys

child = pexpect.spawn('wool', encoding='utf-8')

# Wait for initial prompt
child.expect('    1     wool     › ')
print("Got prompt 1")

# Send first command (hey)
child.sendline('hey')
child.expect('No provider configured.')
print("Got No provider error")

# Wait for second prompt
child.expect('    1     wool     › ', timeout=3)
print("Got prompt 1 again, bug fixed!")

child.sendline('/exit')
