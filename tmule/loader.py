import yaml
import os.path

# This is a solution provided by Josh Bode in stackoverflow to provide import
# https://stackoverflow.com/questions/528281/how-can-i-include-an-yaml-file-inside-another
class Loader(yaml.SafeLoader):

    def __init__(self, stream):

        self._root = os.path.split(stream.name)[0]

        super(Loader, self).__init__(stream)

    def include(self, node):

        data = []
        for file in str(self.construct_scalar(node)).split(' '):
            if (file[:1] == '$'):
                filename = os.path.expandvars(file)
            else:
                filename = os.path.join(self._root, file)
            with open(filename, 'r') as f:
                data += yaml.load(f, Loader)
        return data

Loader.add_constructor('!include', Loader.include)