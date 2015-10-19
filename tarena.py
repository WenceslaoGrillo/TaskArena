# -*- coding: utf-8 -*-


# TaskArena - Adding collaborative functionality to TaskWarrior
# Copyright (C) 2015  Nikolai Nowaczyk
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import click
from tarenalib.arena import uda_config_list
from tarenalib.io import IOManager
import subprocess
import locale

iom = IOManager()

def execute_command(command_args):
    p = subprocess.Popen(command_args,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         )
    encoding = locale.getdefaultlocale()[1]
    p.communicate(input='y\n'.encode(encoding))


@click.group()
@click.option('--file')
def cli(file):
    iom.configfile_name = file


@cli.command(help='Installs TaskArena.')
def install():
    for uda in uda_config_list:
        execute_command(['task', 'config', uda[0], uda[1]])
    iom.send_message('Installation successful.')
    return 0


@cli.command(help='Uninstalls TaskArena.')
def uninstall():
    for uda in uda_config_list:
        execute_command(['task', 'config', uda[0]])
    iom.send_message('Uninstallation successful.')
    return 0


@cli.command(help='Creates a new arena.')
def create():
    te = iom.get_task_emperor()
    if te:
        iom.send_message("Creating new Arena:")
        name = iom.get_input('Enter a name: ')
        ldata = iom.get_input('Enter local data.location: ')
        rdata = iom.get_input('Enter remote data.location: ')
        if te.create_arena(name, ldata, rdata):
            iom.send_message("Arena " + name + " created.")
            iom.save_task_emperor(te)
        else:
            iom.send_message("Arena " + name + " already exists!")
        return 0


@cli.command(help='Deletes ARENA.')
@click.argument('arena')
def delete(arena):
    iom.send_message("Deleting arena %s" % arena)
    return 0


@cli.command(help='Lists all arenas.')
def ls():
    te = iom.get_task_emperor()
    if te.arenas:
        iom.send_message("The following arenas are available:", 1)
        for arena in te.arenas:
            iom.send_message(arena.name, 1)
            iom.send_message("local : " + arena.local_data)
            iom.send_message("remote: " + arena.remote_data, 0, 1)
    else:
        iom.send_message("No arenas found.")


@cli.command(help='Adds tasks matching PATTERN to ARENA.')
@click.argument('arena')
@click.argument('pattern')
def add(arena, pattern):
    iom.send_message("The following tasks will be added to %s" % arena)
    iom.send_message("Applied filter %s" % pattern)
    return 0


@cli.command(help='Removes tasks matching PATTERN from ARENA.')
@click.argument('arena')
@click.argument('pattern')
def remove(arena, pattern):
    iom.send_message("The following tasks will be removed from %s" % arena)
    iom.send_message("Applied filter %s" % pattern)
    return 0


@cli.command(help='Synchronizes ARENA (=all if left blank)')
@click.argument('arena', nargs=-1)
def sync(arena):
    if arena:
        iom.send_message("Syncing %s" % arena)
    else:
        iom.send_message("Syncing everything.")
    return 0


if __name__ == '__main__':
    cli()
