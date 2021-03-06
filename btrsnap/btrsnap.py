#!/usr/bin/python3
'''
Writen for python 3.x
btrsnap is a BTRFS wrapper to simplify working with timestamped snapshots.
'''

import os
import re
import datetime
import subprocess


class PathError(Exception):
    '''
    Path does not exist on the filesystem
    '''
    pass


class TargetError(Exception):
    '''
    There is not exactly 1 symlink inside the snapshot directory
    '''
    pass


class BtrfsError(Exception):
    '''
    btrfs-progs returned a non zero exit code
    '''
    pass


class Path:
    '''
    Base Class for working with filesystem paths
    '''
    def __init__(self, path):
        '''
        Verifies that a path exists.

        Args:
            * path (str): a path on a filesystem.

        Attributes:
            * path (str): absolute path.

        Raises:
            * PathError: invalid path.
        '''
        if os.path.isdir(os.path.expanduser(path)):
            self.path = os.path.abspath(os.path.expanduser(path))
        else:
            raise PathError('Path not valid')


class SnapshotsMixin:
    '''
    Mixin to display btrsnap snapshots in self.path
    '''

    def snapshots(self):
        '''
        List folders in self.path with a name matching a btrsnap timestamp.

        Returns:
            * (list(str)): a list of directories inside self.path that
              match the btrsnap timestamp YYYY-MM-DD-####
        '''
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}-\d{4}$')
        contents = os.listdir(path=self.path)
        contents = [d for d in contents
                    if os.path.isdir(os.path.join(self.path, d))
                    and re.search(pattern, d)]
        contents.sort(reverse=True)
        return contents


class SnapDeep(Path):
    '''
    Generates a list of SnapPath objects for each valid subdirectory of path.

    Args:
        * path (str): path on the filesystem.

    Attributes:
        * path (str): absolute path on the filesystem.

    Raises:
        * PathError
    '''

    def snap_paths(self):
        '''
        Returns:
            * (list(SnapPath): a list of SnapPath objects for each subdirectory
            of self.path.
        '''
        snap_paths = []
        contents = os.listdir(self.path)
        contents = [os.path.join(self.path, d) for d in contents
                    if os.path.isdir(os.path.join(self.path, d))]
        for content in contents:
            try:
                snap_paths.append(SnapPath(content))
            except Exception:
                pass
        return snap_paths


class ReceiveDeep(Path):
    '''
    Generates a list of ReceivePath objects for each valid subdirectory of
    path.

    Args:
        * path (str): path on the filesystem.

    Attributes:
        * path (str): absolute path on the filesystem.

    Raises:
        * PathError
    '''

    def receive_paths(self):
        '''
        Returns:
            * (list(ReceivePath): a list of ReceivePath objects for each
            subdirectory of self.path.
        '''
        receive_paths = []
        contents = os.listdir(self.path)
        contents = [d for d in contents
                    if os.path.isdir(os.path.join(self.path, d))]
        for content in contents:
            try:
                receive_paths.append(ReceivePath(os.path.join(
                    self.path, content)))
            except Exception:
                pass
        return receive_paths


class SnapPath(Path, SnapshotsMixin):
    '''
    Verifies that path exists, and that it contains a symlink.

    Agruments:
        * path (str): path on filesystem

    Attributes:
        * target (str): Absolute path where the symlink points.
        * path (str): Absolute path on the filesystem

    Raises:
        * TargetError:
        * PathError:
    '''
    def __init__(self, path):
        Path.__init__(self, path)
        self.target = 'initiate'

    @property
    def target(self):
        return self._target

    @target.setter
    def target(self, garbage):
        contents = os.listdir(path=self.path)
        contents = [link for link in contents
                    if os.path.islink(os.path.join(self.path, link))]
        if not len(contents) == 1:
            raise TargetError('there must be exactly 1 symlink pointing to a'
                              ' target BTRFS subvolume in snapshot'
                              ' directory {}'.format(self.path))
        self._target = os.path.realpath(os.path.abspath(os.path.join(
                                        self.path, contents[0])))

    def timestamp(self, counter=1):
        '''
        Returns the next availible timestamp in self.path

        Arguments:
            * counter (int): start number for last 4 digits of timestamp.

        Returns:
            * (str): next availible timestamp
        '''
        today = datetime.date.today()
        snapshots = self.snapshots()
        if snapshots:
            last_snapshot = snapshots[0]
            less_than_last_snapshot = True
        else:
            last_snapshot = None
            less_than_last_snapshot = False
        timestamp = None

        while (timestamp is None or timestamp in snapshots
               or less_than_last_snapshot is True):
            timestamp = '{}-{:04d}'.format(today.isoformat(), counter)
            if less_than_last_snapshot is True:
                if timestamp <= last_snapshot:
                    less_than_last_snapshot = True
                else:
                    less_than_last_snapshot = False

            if counter > 9999:
                raise Exception('More than 9999 snapshots created today.'
                                ' Something is probably wrong. Aborting!')
            counter += 1
        return timestamp


class ReceivePath(Path, SnapshotsMixin):
    '''
    Verifies Path and lists Snapshots inside self.path

    Args:
        * Path (str): Path on filesystem

    Attributes:
        * path (str): absolute path
        * Snapshots (list(str)): List of snapshots inside self.path

    Raises:
        * PathError:
    '''
    pass


class Btrfs(Path):
    '''
    Wrapper class for BTRFS functions

    Args:
        * Path (str): Path on filesystem

    Attributes:
        * path (str): absolute path

    Raises:
        * PathError:
    '''

    def snap(self, target, timestamp, readonly=True):
        '''
        Create a snapshot in self.path

        Args:
            * target (str): absolute path of BTRFS subvolume to be cloned.
            * timestamp (str): name of the snapshot to be created.
            * readonly (bool): True/False, new snapshot is readonly.

        Raises:
            * BtrfsError:
        '''
        snapshot = os.path.join(self.path, timestamp)
        if readonly:
            args = ['btrfs', 'subvolume', 'snapshot', '-r', target, snapshot]
        else:
            args = ['btrfs', 'subvolume', 'snapshot', target, snapshot]

        return_code = subprocess.call(args)
        if return_code:
            raise BtrfsError('BTRFS failed to create a snapshot'
                             ' of {} in \'{}\''.format(target, snapshot))

    def unsnap(self, timestamp):
        '''
        Delete a snapshot in self.path

        Args:
            * timestamp (str): name of the snapshot to be deleted.

        Raises:
            * BtrfsError:
        '''
        snapshot = os.path.join(self.path, timestamp)
        args = ['btrfs', 'subvolume', 'delete', snapshot]
        return_code = subprocess.call(args)
        if return_code:
            raise BtrfsError('BTRFS failed to delete the subvolume.'
                             ' Perhaps you need root permissions')

    def send(self, snapshot, parent=None):
        '''
        Send a snapshot using btrfs-progs.

        Args:
            * snapshot (str): absolute path of snapshot to be sent.
            * parent (str): absolute path of parent snapshot alread on
            receiving filesystem.

        Returns:
            * (subprocess.Popen): can be used to pipe output to receive.
        '''
        args = ['btrfs', 'send']
        if parent:
            parent = os.path.join(self.path, parent)
            args.extend(['-p', parent])

        args.append(os.path.join(self.path, snapshot))
        p1 = subprocess.Popen(args, stdout=subprocess.PIPE)
        return p1

    def receive(self, p1):
        '''
        Receive a snapshot using btrfs-progs.

        Args:
            * p1 (subprocess.Popen): send process

        Raises:
            * BtrfsError:
        '''
        args = ['btrfs', 'receive', self.path]
        p2 = subprocess.Popen(args, stdin=p1.stdout,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p2.communicate()
        p1.stdout.close()
        if p2.returncode:
            raise BtrfsError('BTRFS Failed send/recieve.'
                             ' Do you have root permissions?',
                             output[0], output[1])


def snap(path, readonly=True):
    '''
    Creates a snapshot inside PATH with format YYYY-MM-DD-####
    of the subvolume pointed to by the symlink inside PATH.

    Args:
        * path (str): path on filesystem
        * readonly (bool): create readonly snapshot?
    '''
    snappath = SnapPath(path)
    btrfs = Btrfs(snappath.path)
    btrfs.snap(snappath.target, snappath.timestamp(), readonly=readonly)


def unsnap(path, keep=5):
    '''
    Delete all but most recent KEEP(default 5) snapshots inside PATH

    Args:
        * path (str): path on filesystem
        * keep (int): number of snapshots to keep

    Returns:
        * msg (str): results
    '''
    snappath = ReceivePath(path)
    btrfs = Btrfs(snappath.path)
    snapshots = snappath.snapshots()

    if not keep >= 0 or not isinstance(keep, int):
        raise Exception('keep must be a positive integer')
    if len(snapshots) > keep:
        snaps_to_delete = snapshots[keep:]
        for snapshot in snaps_to_delete:
            btrfs.unsnap(snapshot)
        msg = 'Deleted {} snapshot(s) from "{}". {} kept'.format(
            len(snaps_to_delete), snappath.path, keep)
    else:
        msg = ('There are less than {} snapshot(s) in "{}"...'
               ' not deleting any'.format(keep, snappath.path))
    return msg


def unsnap_deep(path, keep=5):
    '''
    Delete all but KEEP (default 5) snapshots from each directory
    inside of path

    Args:
        * path (str): path on filesystem
        * keep (int): number of snapshots to keep

    Returns:
        * msg (str): results
    '''
    msg = []
    receive_deep = ReceiveDeep(path)
    receive_paths = receive_deep.receive_paths()
    receive_paths = [path.path for path in receive_paths]
    if len(receive_paths) == 0:
        msg = 'No subdirectories found in \'{}\''.format(receive_deep.path)
        return msg
    for path in receive_paths:
        msg.append(unsnap(path, keep))
    return '\n'.join(msg)


def snapdeep(path, readonly=True):
    '''
    Create a snapshot in each subdirectory in PATH.

    Args:
        * path (str): path on filesystem
        * readonly (bool): Create readonly snapshots?

    Returns:
        * msg (str): results
    '''
    snapdeep = SnapDeep(path)
    snap_paths = snapdeep.snap_paths()
    if len(snap_paths) == 0:
        msg = 'No snapshot directories found in \'{}\''.format(snapdeep.path)
        return msg
    for snap_path in snap_paths:
        snap(snap_path.path, readonly=readonly)


def show_snaps(path):
    '''
    List snapshots inside PATH.

    Args:
        * path (str): path on filesystem.

    Returns:
        * msg (str): results
    '''
    receive_path = ReceivePath(path)
    snapshots = receive_path.snapshots()
    msg = []
    for snapshot in snapshots:
        msg.append(snapshot)
    msg.append('\n"{}" contains {} snapshot(s)'.format(
        receive_path.path, len(snapshots)))
    return '\n'.join(msg)


def show_snaps_deep(path):
    '''
    Recursively list snapshots inside PATH.

    Args:
        * path (str): Path on filesystem.

    Returns:
        * msg (str): results
    '''
    msg = []
    overall_snapshot_count = 0
    overall_path_count = 0
    receive_deep = ReceiveDeep(path)
    receive_paths = receive_deep.receive_paths()
    for p in receive_paths:
        snapshots = p.snapshots()
        msg.append('\n\'{}\'/'.format(p.path))
        if snapshots:
            newest = snapshots[0]
            oldest = snapshots[-1]
            msg.append('\t{} snapshots: Newest = {}, Oldest = {}'.format(
                len(snapshots), newest[:-5], oldest[:-5]))
            for snapshot in snapshots:
                msg.append('\t\t{}'.format(snapshot))
                overall_snapshot_count += 1
        else:
            msg.append('\t\tNo snapshots')
        overall_path_count += 1
    msg.append('\n{:{s}^{n}}'.format(' Summary ', s='-', n=60))
    msg.append('\'{}\' contains {} snapshots in {} subdirectories'.format(
        path, overall_snapshot_count, overall_path_count))

    return '\n'.join(msg)


def sendreceive(send_path, receive_path):
    '''
    Send snapshots from one BTRFS PATH to another.

    Args:
        * send_path: path to snapshot to send
        * receive_path: path to receive snapshot in.

    Returns:
        * (str): results
    '''
    send = SnapPath(send_path)
    receive = ReceivePath(receive_path)
    send_btr = Btrfs(send.path)
    receive_btr = Btrfs(receive.path)

    send_set = set(send.snapshots())
    receive_set = set(receive.snapshots())
    diff = send_set - receive_set
    diff = list(diff)
    diff.sort()
    union = send_set & receive_set
    union = list(union)
    union.sort()

    number_sent = len(diff)

    if diff:
        if union and union[-1] < diff[0]:
            parent, snapshot = union[-1], diff[0]
            p1 = send_btr.send(snapshot, parent)
            receive_btr.receive(p1)
        else:
            parent, snapshot = None, diff[0]
            p1 = send_btr.send(snapshot, parent)
            receive_btr.receive(p1)
        while diff:
            if len(diff) >= 2:
                parent, snapshot = diff.pop(0), diff[0]
                p1 = send_btr.send(snapshot, parent)
                receive_btr.receive(p1)
            else:
                diff.pop(0)
        msg = '{} snapshots copied from \'{}\' to \'{}\''.format(
            number_sent, send.path, receive.path)
    else:
        msg = 'No new snapshots to copy from \'{}\' to \'{}\''.format(
            send.path, receive.path)
    return msg


def sendreceive_deep(send_path, receive_path):
    '''
    Send all snapshots in subdirectories of send_path to receive_path.

    Args:
        * send_path (str): absolute path holding one or more snapshot
                         directories.
        * receive_path (str): absolute path to receive snapshot directories in.

    Returns:
        * (str): results.
    '''
    snappaths = SnapDeep(send_path)
    snappaths = snappaths.snap_paths()
    snappaths = [snappath.path for snappath in snappaths]
    receive_path = Path(receive_path)
    receive_path = receive_path.path
    receive_paths = [os.path.join(receive_path, s.split(os.path.sep)[-1]) for
                     s in snappaths]
    msg = []

    for p in receive_paths:
        if not os.path.isdir(p):
            os.mkdir(p)

    args = zip(snappaths, receive_paths)
    for send_path, receive_path in args:
        msg.append(sendreceive(send_path, receive_path))
    return '\n'.join(msg)


def main():
    '''
    Command Line Interface.
    '''

    import argparse

    def caller(func, *args, **kargs):
        try:
            msg = func(*args, **kargs)
            if msg:
                print(msg)
        except Exception as err:
            print('Error:', err)

    def run_snap(args):
        keep = None
        if args.delete:
            keep = 5
            if args.keep:
                keep = args.keep[0]
        if not args.recursive:
            caller(snap, args.snap_path[0])
            if not keep is None:
                caller(unsnap, args.snap_path[0], keep=keep)
        if args.recursive:
            caller(snapdeep, args.snap_path[0])
            if not keep is None:
                caller(unsnap_deep, args.snap_path[0], keep=keep)

    def run_list(args):
        if not args.recursive:
            caller(show_snaps, args.snap_path[0])
        else:
            caller(show_snaps_deep, args.snap_path[0])

    def run_send(args):
        if not args.recursive:
            caller(sendreceive, args.send_path[0], args.receive_path[0])

        if args.recursive:
            caller(sendreceive_deep, args.send_path[0], args.receive_path[0])

    def run_delete(args):
        keep = 5
        if args.keep:
            keep = args.keep[0]
        if args.recursive:
            caller(unsnap_deep, args.snap_path[0], keep=keep)
        else:
            caller(unsnap, args.snap_path[0], keep=keep)

    def no_sub(args):
        parser.parse_args('--help')

    parser = argparse.ArgumentParser(
        prog='btrsnap',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='''
    btrsnap is a BTRFS wrapper to simplify dealing with snapshots.
    You will need root privileges for some actions.


    To use, create a root directory on a BTRFS filesystem where you will keep
    your snapshots. Within this directory create any number of subdirectories.
    Inside each subdirectory create a symbolic link that points to the BTRFS
    subvolume you wish to create snapshots of.

    For example:

            /snapshots
                -/music
                    target (symbolic link pointing to => /srv/music)
                -/photos
                    target (symbolic link pointing to => /srv/photos)

    Note:
            You can create a symbolic link using:
            ln -s /srv/music /snapshots/music/target
    ...         ''')
    parser.add_argument('--version', action='version',
                        version='%(prog)s 1.1.1'
                        )
    subparsers = parser.add_subparsers(title='sub-commands')

    subparser_snap = subparsers.add_parser('snap',
                                           description='Creates a new'
                                           ' timestamped BTRFS snapshot'
                                           ' in PATH. The snapshot will'
                                           ' be of the BTRFS subvolume'
                                           ' pointed to by the symbolic'
                                           ' link in PATH.',
                                           help='Creates new timestamped BTRFS'
                                           ' snapshot'
                                           )
    subparser_snap.add_argument('-r', '--recursive',
                                action='store_true',
                                help='Instead, create a snapshot in each'
                                ' subdirectory of PATH.'
                                )
    subparser_snap.add_argument('-d', '--delete',
                                action='store_true',
                                help='Delete all but 5 snapshots in PATH.'
                                ' May be modified by -k, --keep'
                                )
    subparser_snap.add_argument('-k', '--keep',
                                nargs=1,
                                type=int,
                                metavar='N',
                                help='keep N snapshots when deleting.'
                                )
    subparser_snap.add_argument('snap_path',
                                nargs=1,
                                metavar='PATH',
                                help='A directory on a BTRFS file system with'
                                ' a symlink pointing to a BTRFS subvolume'
                                )
    subparser_snap.set_defaults(func=run_snap)

    subparser_list = subparsers.add_parser('list',
                                           description='Show timestamped'
                                           ' snapshots in PATH',
                                           help='Show timestamped snapshots'
                                           )
    subparser_list.add_argument('snap_path',
                                nargs=1,
                                metavar='PATH',
                                help='A directory on a BTRFS filesystem'
                                ' that contains snapshots created by btrsnap.'
                                )
    subparser_list.add_argument('-r', '--recursive',
                                action='store_true',
                                help='Instead, show summary statistics for all'
                                ' subdirectories in PATH.'
                                )
    subparser_list.set_defaults(func=run_list)

    subparser_delete = subparsers.add_parser('delete',
                                             description='Delete all but KEEP'
                                             ' snapshots from PATH.'
                                             ' (Default, KEEP=5)',
                                             help='Delete snapshots'
                                             )
    subparser_delete.add_argument('-k', '--keep',
                                  nargs=1,
                                  type=int,
                                  metavar='N',
                                  help='keep N snapshots when deleting.'
                                  )
    subparser_delete.add_argument('-r', '--recursive',
                                  action='store_true',
                                  help='Instead delete all but KEEP snapshots'
                                  ' from each subdirectory')
    subparser_delete.add_argument('snap_path',
                                  nargs=1,
                                  metavar='PATH',
                                  help='A directory on a BTRFS filesystem'
                                  ' that contains snapshots created by'
                                  ' btrsnap.'
                                  )
    subparser_delete.set_defaults(func=run_delete)

    subparser_send = subparsers.add_parser('send',
                                           description='Send all snapshots'
                                           ' from SendPATH to ReceivePATH if'
                                           ' not present.',
                                           help='Use BTRFS send/receive to'
                                           ' smartly send snapshots from one'
                                           ' BTRFS filesystem to another.'
                                           )
    subparser_send.add_argument('-r', '--recursive',
                                action='store_true',
                                help='Instead, send snapshots from each sub'
                                ' directory of SendPATH to a subdirectory of'
                                ' the same name in ReceivePATH. Subdirectories'
                                ' are automatically created if needed.'
                                )
    subparser_send.add_argument('send_path',
                                nargs=1,
                                metavar='SendPATH',
                                help='A directory on a BTRFS filesystem that'
                                ' contains snapshots created by btrsnap.')
    subparser_send.add_argument('receive_path',
                                nargs=1,
                                metavar='ReceivePATH',
                                help='A directory on a BTRFS filesystem that'
                                ' will receive snapshots.')
    subparser_send.set_defaults(func=run_send)

    args = parser.parse_args()
    try:
        args.func(args)
    except AttributeError:
        no_sub(args)

if __name__ == "__main__":

    # start the program
    main()
