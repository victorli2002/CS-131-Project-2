# The EnvironmentManager class keeps a mapping between each global variable (aka symbol)
# in a brewin program and the value of that variable - the value that's passed in can be
# anything you like. In our implementation we pass in a Value object which holds a type
# and a value (e.g., Int, 10).
class EnvironmentManager:
  def __init__(self):
    self.layers = [{}]
    self.num_layers = 0
    #we assume that all references are on the top level func scope

  # Gets the data associated a variable name
  def get(self, symbol):
    i = self.num_layers
    while i >= 0:
      env = self.layers[i]
      if symbol in env:
        try: #reference
          ref_env, value = env[symbol]
          return ref_env.get(value)
        except: #value
          return env[symbol]
      i -= 1
    return None

  # associates data with new var name
  def new_var(self, symbol, value = None, ref = False, ref_env = None):
    if ref: #reference
      (self.layers[-1])[symbol] = (ref_env, value)
      return
    (self.layers[-1])[symbol] = value

  # top level var
  def new_base(self, symbol, value):
    (self.layers[0])[symbol] = value
  
  # Changes the data associated with a variable name
  def change_var(self, symbol, value):
    i = self.num_layers
    while i >= 0:
      env = self.layers[i]
      if symbol in env:
        try: #reference
          ref_env, ref_to = env[symbol]
          ref_env.change_var(ref_to, value)
        except: #value
          env[symbol] = value
        return
      i -= 1
    raise Exception(f'Unknown variable: {symbol}')
  
  def has_var(self, symbol):
    i = self.num_layers
    while i >= 0:
      env = self.layers[i]
      if symbol in env:
        return True
      i -= 1
    return False
  
  def has_var_in_block(self, symbol):
    return symbol in self.layers[-1]

  def new_layer(self):
    self.layers.append({})
    self.num_layers += 1

  def kill_layer(self):
    self.layers.pop()
    self.num_layers -= 1
