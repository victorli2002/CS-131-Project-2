from enum import Enum
from intbase import InterpreterBase, ErrorType
from env_v2 import EnvironmentManager
from tokenize import Tokenizer
from func_v2 import FunctionManager

# Enumerated type for our different language data types
class Type(Enum):
  INT = 1
  BOOL = 2
  STRING = 3

# Represents a value, which has a type and its value
class Value:
  def __init__(self, type, value = None):
    self.t = type
    self.v = value

  def value(self):
    return self.v

  def set(self, other):
    self.t = other.t
    self.v = other.v

  def type(self):
    return self.t

# Main interpreter class
class Interpreter(InterpreterBase):
  def __init__(self, console_output=True, input=None, trace_output=False):
    super().__init__(console_output, input)
    self._setup_operations()  # setup all valid binary operations and the types they work on
    self.trace_output = trace_output

  # run a program, provided in an array of strings, one string per line of source code
  def run(self, program):
    self.program = program
    self._compute_indentation(program)  # determine indentation of every line
    self.tokenized_program = Tokenizer.tokenize_program(program)
    self.func_manager = FunctionManager(self.tokenized_program)
    self.env_stack = []
    self.result_stack = []
    self.ip = self._find_first_instruction(InterpreterBase.MAIN_FUNC)
    self.return_stack = []
    self.terminate = False
    #self.global_env = EnvironmentManager() # used to track variables/scope

    # main interpreter run loop
    while not self.terminate:
      self._process_line()

  def _process_line(self):
    if self.trace_output:
      print(f"{self.ip:04}: {self.program[self.ip].rstrip()}")
    tokens = self.tokenized_program[self.ip]
    if not tokens:
      self._blank_line()
      return

    args = tokens[1:]

    match tokens[0]:
      case InterpreterBase.VAR_DEF:
        self._vardef(args)
        self._advance_to_next_statement()
      case InterpreterBase.ASSIGN_DEF:
        self._assign(args)
      case InterpreterBase.FUNCCALL_DEF:
        self._funccall(args)
      case InterpreterBase.ENDFUNC_DEF:
        #self._endfunc()
        self._return(False)
      case InterpreterBase.IF_DEF:
        self._if(args)
      case InterpreterBase.ELSE_DEF:
        self._else()
      case InterpreterBase.ENDIF_DEF:
        self._endif()
      case InterpreterBase.RETURN_DEF:
        self._return(args)
      case InterpreterBase.WHILE_DEF:
        self._while(args)
      case InterpreterBase.ENDWHILE_DEF:
        self._endwhile(args)
      case default:
        raise Exception(f'Unknown command: {tokens[0]}')

  def _blank_line(self):
    self._advance_to_next_statement()

  def _vardef(self, args):
    type = args[0]
    for a in args[1:]:
      if self.env_stack[-1].has_var_in_block(a):
        super().error(ErrorType.NAME_ERROR,f"Cannot redefine variables in the same block", self.ip)
      match type:
        case InterpreterBase.INT_DEF:
          self.env_stack[-1].new_var(a,Value(Type.INT, 0))
        case InterpreterBase.BOOL_DEF:
          self.env_stack[-1].new_var(a,Value(Type.BOOL, False))
        case InterpreterBase.STRING_DEF:
          self.env_stack[-1].new_var(a,Value(Type.STRING, ""))
        case _:
          raise Exception(f'Unknown type: {type}')

  def _assign(self, tokens):
    if len(tokens) < 2:
      super().error(ErrorType.SYNTAX_ERROR,f"Invalid assignment statement", self.ip) #no
    vname = tokens[0]
    value_type = self._eval_expression(tokens[1:])
    if self.env_stack[-1].has_var(vname) == False:
      super().error(ErrorType.NAME_ERROR,f"Cannot reference variable without defining it", self.ip)
    if (self._get_value(vname)).type() != value_type.type():
      super().error(ErrorType.TYPE_ERROR,f"Incompatible assignment", self.ip)
    self._set_value(vname, value_type)
    self._advance_to_next_statement()

  def _funccall(self, args):
    if not args:
      super().error(ErrorType.SYNTAX_ERROR,f"Missing function name to call", self.ip) #!
    if args[0] == InterpreterBase.PRINT_DEF:
      self._print(args[1:])
      self._advance_to_next_statement()
    elif args[0] == InterpreterBase.INPUT_DEF:
      self._input(args[1:])
      self._advance_to_next_statement()
    elif args[0] == InterpreterBase.STRTOINT_DEF:
      self._strtoint(args[1:])
      self._advance_to_next_statement()
    else:
      self.return_stack.append(self.ip+1)
      if len(args) > 1:
        self.ip = self._find_first_instruction(args[0], args[1:])
      else:
        self.ip = self._find_first_instruction(args[0])

  def _endfunc(self):
    if not self.return_stack:  # done with main!
      self.terminate = True
    else:
      self.ip = self.return_stack.pop()

  def _if(self, args):
    if not args:
      super().error(ErrorType.SYNTAX_ERROR,f"Invalid if syntax", self.ip) #no
    value_type = self._eval_expression(args)
    if value_type.type() != Type.BOOL:
      super().error(ErrorType.TYPE_ERROR,f"Non-boolean if expression", self.ip) #!
    # create new env layer
    self.env_stack[-1].new_layer()
    if value_type.value():
      self._advance_to_next_statement()
      return
    else:
      for line_num in range(self.ip+1, len(self.tokenized_program)):
        tokens = self.tokenized_program[line_num]
        if not tokens:
          continue
        if (tokens[0] == InterpreterBase.ENDIF_DEF or tokens[0] == InterpreterBase.ELSE_DEF) and self.indents[self.ip] == self.indents[line_num]:
          if tokens[0] == InterpreterBase.ENDIF_DEF:
            self.env_stack[-1].kill_layer()
          self.ip = line_num + 1
          return
    super().error(ErrorType.SYNTAX_ERROR,f"Missing endif", self.ip) #no

  def _endif(self):
    self.env_stack[-1].kill_layer()
    self._advance_to_next_statement()

  def _else(self):
    self.env_stack[-1].kill_layer()
    for line_num in range(self.ip+1, len(self.tokenized_program)):
      tokens = self.tokenized_program[line_num]
      if not tokens:
        continue
      if tokens[0] == InterpreterBase.ENDIF_DEF and self.indents[self.ip] == self.indents[line_num]:
          self.ip = line_num + 1
          return
    super().error(ErrorType.SYNTAX_ERROR,f"Missing endif", self.ip) #no

  def _return(self,args):
    return_type = self.result_stack.pop()
    default = False

    #handle default returns or evaluate argument
    if not args:
      if return_type != InterpreterBase.VOID_DEF:
        default = True
      else:
        self.env_stack.pop()
        self._endfunc()
        return
    else:
      value_type = self._eval_expression(args)

    #go to outer environment
    self.env_stack.pop()
    #create result variable if it doesn't exist
    match return_type:
      case InterpreterBase.INT_DEF:
        res = 'resulti'
      case InterpreterBase.BOOL_DEF:
        res = 'resultb'
      case InterpreterBase.STRING_DEF:
        res = 'results'
      case InterpreterBase.VOID_DEF:        #error if we have any arguments for a void func
        super().error(ErrorType.TYPE_ERROR,f"Invalid return type", self.ip)
    #default assignment (can reset result variable if it was something else)
    if not self.env_stack[-1].has_var(res):
      self._default_assignment(return_type)
    #non-default assignment
    if default == False:
      self._set_value(res, value_type)
    self._endfunc()

  def _default_assignment(self, type):
    match type:
      case InterpreterBase.INT_DEF:
        self.env_stack[-1].new_base("resulti", Value(Type.INT, 0))
      case InterpreterBase.BOOL_DEF:
        self.env_stack[-1].new_base("resultb", Value(Type.BOOL, False))
      case InterpreterBase.STRING_DEF:
        self.env_stack[-1].new_base("results", Value(Type.STRING, ""))
      case _:
        raise Exception(f'Unknown type: {type}')

  def _while(self, args):
    if not args:
      super().error(ErrorType.SYNTAX_ERROR,f"Missing while expression", self.ip) #no
    value_type = self._eval_expression(args)
    if value_type.type() != Type.BOOL:
      super().error(ErrorType.TYPE_ERROR,f"Non-boolean while expression", self.ip) #!
    if value_type.value() == False:
      self._exit_while()
      return
    # If true, we advance to the next statement
    self.env_stack[-1].new_layer()
    self._advance_to_next_statement()

  def _exit_while(self):
    while_indent = self.indents[self.ip]
    cur_line = self.ip + 1
    while cur_line < len(self.tokenized_program):
      if len(self.tokenized_program[cur_line]) == 0:
        cur_line += 1 
        continue
      if self.tokenized_program[cur_line][0] == InterpreterBase.ENDWHILE_DEF and self.indents[cur_line] == while_indent:
        self.ip = cur_line + 1
        return
      if self.tokenized_program[cur_line] and self.indents[cur_line] < self.indents[self.ip]:
        break # syntax error!
      cur_line += 1
    # didn't find endwhile
    super().error(ErrorType.SYNTAX_ERROR,f"Missing endwhile", self.ip) #no

  def _endwhile(self, args):
    self.env_stack[-1].kill_layer()
    while_indent = self.indents[self.ip]
    cur_line = self.ip - 1
    while cur_line >= 0:
      if len(self.tokenized_program[cur_line]) == 0:
        cur_line -= 1 
        continue
      if self.tokenized_program[cur_line][0] == InterpreterBase.WHILE_DEF and self.indents[cur_line] == while_indent:
        self.ip = cur_line
        return
      if self.tokenized_program[cur_line] and self.indents[cur_line] < self.indents[self.ip]:
        break # syntax error!
      cur_line -= 1
    # didn't find while
    super().error(ErrorType.SYNTAX_ERROR,f"Missing while", self.ip) #no

  def _print(self, args):
    if not args:
      super().error(ErrorType.SYNTAX_ERROR,f"Invalid print call syntax", self.ip) #no
    out = []
    for arg in args:
      val_type = self._get_value(arg)
      out.append(str(val_type.value()))
    super().output(''.join(out))

  def _input(self, args):
    if args:
      self._print(args)
    result = super().get_input()
    if not self.env_stack[-1].has_var('results'):
      self._default_assignment(InterpreterBase.STRING_DEF)
    self._set_value('results', Value(Type.STRING, result))   # return always passed back in results

  def _strtoint(self, args):
    if len(args) != 1:
      super().error(ErrorType.SYNTAX_ERROR,f"Invalid strtoint call syntax", self.ip) #no
    value_type = self._get_value(args[0])
    if value_type.type() != Type.STRING:
      super().error(ErrorType.TYPE_ERROR,f"Non-string passed to strtoint", self.ip) #!
    if not self.env_stack[-1].has_var('resulti'):
      self._default_assignment(InterpreterBase.INT_DEF)
    self._set_value('resulti', Value(Type.INT, int(value_type.value())))   # return always passed back in result

  def _advance_to_next_statement(self):
    # for now just increment IP, but later deal with loops, returns, end of functions, etc.
    self.ip += 1

  # create a lookup table of code to run for different operators on different types
  def _setup_operations(self):
    self.binary_op_list = ['+','-','*','/','%','==','!=', '<', '<=', '>', '>=', '&', '|']
    self.binary_ops = {}
    self.binary_ops[Type.INT] = {
     '+': lambda a,b: Value(Type.INT, a.value()+b.value()),
     '-': lambda a,b: Value(Type.INT, a.value()-b.value()),
     '*': lambda a,b: Value(Type.INT, a.value()*b.value()),
     '/': lambda a,b: Value(Type.INT, a.value()//b.value()),  # // for integer ops
     '%': lambda a,b: Value(Type.INT, a.value()%b.value()),
     '==': lambda a,b: Value(Type.BOOL, a.value()==b.value()),
     '!=': lambda a,b: Value(Type.BOOL, a.value()!=b.value()),
     '>': lambda a,b: Value(Type.BOOL, a.value()>b.value()),
     '<': lambda a,b: Value(Type.BOOL, a.value()<b.value()),
     '>=': lambda a,b: Value(Type.BOOL, a.value()>=b.value()),
     '<=': lambda a,b: Value(Type.BOOL, a.value()<=b.value()),
    }
    self.binary_ops[Type.STRING] = {
     '+': lambda a,b: Value(Type.STRING, a.value()+b.value()),
     '==': lambda a,b: Value(Type.BOOL, a.value()==b.value()),
     '!=': lambda a,b: Value(Type.BOOL, a.value()!=b.value()),
     '>': lambda a,b: Value(Type.BOOL, a.value()>b.value()),
     '<': lambda a,b: Value(Type.BOOL, a.value()<b.value()),
     '>=': lambda a,b: Value(Type.BOOL, a.value()>=b.value()),
     '<=': lambda a,b: Value(Type.BOOL, a.value()<=b.value()),
    }
    self.binary_ops[Type.BOOL] = {
     '&': lambda a,b: Value(Type.BOOL, a.value() and b.value()),
     '==': lambda a,b: Value(Type.BOOL, a.value()==b.value()),
     '!=': lambda a,b: Value(Type.BOOL, a.value()!=b.value()),
     '|': lambda a,b: Value(Type.BOOL, a.value() or b.value())
    }

  def _compute_indentation(self, program):
    self.indents = [len(line) - len(line.lstrip(' ')) for line in program]

  def _find_first_instruction(self, funcname, args = None):
    func_info = self.func_manager.get_function_info(funcname)
    if func_info == None:
      super().error(ErrorType.NAME_ERROR,f"Unable to locate {funcname} function", self.ip) #!
    arg_vals = []
    if args != None:
      for a in args:
        arg_vals.append(self._get_value(a))
    ref_env = self.env_stack[-1] if self.env_stack != [] else None
    self.env_stack.append(EnvironmentManager())
    self.result_stack.append(func_info.return_type)
    if args != None:
      for i, a in enumerate(arg_vals):
        name, type = func_info.args[i]
        is_ref = func_info.refs[i]
        if is_ref: #reference definition
          if ref_env.has_var(args[i]):
            match type:
              case InterpreterBase.INT_DEF:
                type = Type.INT
              case InterpreterBase.BOOL_DEF:
                type = Type.BOOL
              case InterpreterBase.STRING_DEF:
                type = Type.STRING
              case _:
                raise Exception(f'Unknown type: {type}')
            if a.type() != type:
              super().error(ErrorType.TYPE_ERROR,f"Incompatible parameter", self.ip)
            self.env_stack[-1].new_var(name, args[i], True, ref_env)
            continue
        self._vardef([type, name])
        match type:
          case InterpreterBase.INT_DEF:
            type = Type.INT
          case InterpreterBase.BOOL_DEF:
            type = Type.BOOL
          case InterpreterBase.STRING_DEF:
            type = Type.STRING
          case _:
            raise Exception(f'Unknown type: {type}')
        if a.type() != type:
          super().error(ErrorType.TYPE_ERROR,f"Incompatible parameter", self.ip)
        self._set_value(name, a)
    #gotta handle passing in vars here
    return func_info.start_ip

  # given a token name (e.g., x, 17, True, "foo"), give us a Value object associated with it
  def _get_value(self, token):
    if not token:
      super().error(ErrorType.NAME_ERROR,f"Empty token", self.ip) #no
    if token[0] == '"':
      return Value(Type.STRING, token.strip('"'))
    if token.isdigit() or token[0] == '-':
      return Value(Type.INT, int(token))
    if token == InterpreterBase.TRUE_DEF or token == InterpreterBase.FALSE_DEF:
      return Value(Type.BOOL, token == InterpreterBase.TRUE_DEF)
    if self.env_stack[-1].has_var(token) == False:
      super().error(ErrorType.NAME_ERROR,f"Cannot reference variable without defining it", self.ip)
    value = self.env_stack[-1].get(token)
    if value  == None:
      super().error(ErrorType.NAME_ERROR,f"Unknown variable {token}", self.ip) #!
    return value

  # sets value of a var that already exists
  def _set_value(self, varname, value_type):
    if self.env_stack[-1].has_var(varname) == False:
      super().error(ErrorType.NAME_ERROR,f"Cannot reference variable without defining it", self.ip)
    if self._get_value(varname).type() != value_type.type():
      super().error(ErrorType.TYPE_ERROR,f"Mismatching variable type", self.ip)
    self.env_stack[-1].change_var(varname,value_type)

  # evaluate expressions in prefix notation: + 5 * 6 x
  def _eval_expression(self, tokens):
    stack = []

    for token in reversed(tokens):
      if token in self.binary_op_list:
        v1 = stack.pop()
        v2 = stack.pop()
        if v1.type() != v2.type():
          super().error(ErrorType.TYPE_ERROR,f"Mismatching types {v1.type()} and {v2.type()}", self.ip) #!
        operations = self.binary_ops[v1.type()]
        if token not in operations:
          super().error(ErrorType.TYPE_ERROR,f"Operator {token} is not compatible with {v1.type()}", self.ip) #!
        stack.append(operations[token](v1,v2))
      elif token == '!':
        v1 = stack.pop()
        if v1.type() != Type.BOOL:
          super().error(ErrorType.TYPE_ERROR,f"Expecting boolean for ! {v1.type()}", self.ip) #!
        stack.append(Value(Type.BOOL, not v1.value()))
      else:
        value_type = self._get_value(token)
        stack.append(value_type)

    if len(stack) != 1:
      super().error(ErrorType.SYNTAX_ERROR,f"Invalid expression", self.ip) #no

    return stack[0]
